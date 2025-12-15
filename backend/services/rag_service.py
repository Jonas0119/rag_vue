"""
RAG 服务 - 检索增强生成
"""
import os
import uuid
import logging
from typing import List, Dict, Optional, Generator
import time

from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain.messages import HumanMessage, ToolMessage

from backend.utils.config import config
from backend.utils.prompts import RAG_TEMPLATE, DIRECT_ANSWER_TEMPLATE
from .vector_store_service import get_vector_store_service

logger = logging.getLogger(__name__)

# LangGraph RAG（可选）
from .rag_graph import build_rag_graph
from .rag_nodes import (
    create_generate_query_or_respond_node,
    create_grade_documents_node,
    create_rewrite_question_node,
    create_generate_answer_node,
)
from .rag_tools import create_retrieve_tool
from .hybrid_retriever import HybridRetriever
from .reranker import CrossEncoderReranker, RemoteReranker
from .checkpoint_manager import create_checkpointer
from backend.database import ParentChildDAO
from backend.utils.token_counter import token_counter


class RAGService:
    """RAG 问答服务"""
    
    def __init__(self):
        self.vector_service = get_vector_store_service()
        self.llm = self._init_llm()
        self.summary_llm = self._init_summary_llm()  # 用于消息总结的模型
        self.prompt = ChatPromptTemplate.from_template(RAG_TEMPLATE)
        self.direct_prompt = ChatPromptTemplate.from_template(DIRECT_ANSWER_TEMPLATE)
        self.parent_child_dao = ParentChildDAO()
    
    def _init_llm(self):
        """初始化 LLM"""
        # 设置环境变量
        os.environ["ANTHROPIC_API_KEY"] = config.ANTHROPIC_API_KEY
        os.environ["ANTHROPIC_BASE_URL"] = config.ANTHROPIC_BASE_URL
        
        llm = ChatAnthropic(
            model=config.LLM_MODEL,
            temperature=config.LLM_TEMPERATURE,
            max_tokens=config.LLM_MAX_TOKENS
        )
        return llm
    
    def _init_summary_llm(self):
        """初始化用于总结的 LLM（如果启用消息总结）"""
        if not config.USE_MESSAGE_SUMMARIZATION:
            return None
        
        # 设置环境变量
        os.environ["ANTHROPIC_API_KEY"] = config.ANTHROPIC_API_KEY
        os.environ["ANTHROPIC_BASE_URL"] = config.ANTHROPIC_BASE_URL
        
        # 创建总结用的模型
        if config.MESSAGE_SUMMARIZATION_MODEL:
            summary_model = ChatAnthropic(
                model=config.MESSAGE_SUMMARIZATION_MODEL,
                temperature=0.0,  # 总结使用较低温度
                max_tokens=config.MESSAGE_SUMMARIZATION_MAX_TOKENS
            )
        else:
            # 如果没有配置总结模型，使用主模型
            summary_model = self.llm
        
        return summary_model

    def _build_langgraph_graph(self, user_id: int):
        """
        为指定用户构建 LangGraph RAG 工作流（按配置选择 retriever / reranker / parent-child）。
        """
        # retriever
        if config.USE_HYBRID_RETRIEVER:
            retriever = HybridRetriever(user_id=user_id, top_k=config.HYBRID_RETRIEVER_TOP_K)
        else:
            retriever = self.vector_service.get_retriever(user_id, k=config.HYBRID_RETRIEVER_TOP_K)

        # parent-child 映射：给 retriever 注入 parent_map（工具会用来从 child 映射回 parent）
        if config.USE_PARENT_CHILD_STRATEGY and hasattr(retriever, "set_parent_map"):
            parent_map = self.parent_child_dao.get_parent_map_for_user(user_id)
            try:
                retriever.set_parent_map(parent_map)  # type: ignore[attr-defined]
            except Exception:
                pass

        # reranker（可选）
        reranker = None
        if config.USE_RERANKER:
            if config.USE_REMOTE_RERANKER and config.INFERENCE_API_BASE_URL:
                reranker = RemoteReranker(
                    base_url=config.INFERENCE_API_BASE_URL,
                    api_key=config.INFERENCE_API_KEY,
                    timeout=config.INFERENCE_API_TIMEOUT,
                    max_retry=config.INFERENCE_API_MAX_RETRY,
                )
            else:
                reranker = CrossEncoderReranker()

        retrieve_tool = create_retrieve_tool(
            retriever=retriever,
            reranker=reranker,
            top_k=config.RERANK_TOP_K,
            top_n=config.RERANK_TOP_N,
            rerank_score_threshold=config.RERANK_SCORE_THRESHOLD,
        )

        # 节点模型：目前直接复用同一个 ChatAnthropic（MiniMax-M2 via Anthropic）
        response_model = self.llm
        grader_model = self.llm

        generate_query_or_respond = create_generate_query_or_respond_node(response_model, retrieve_tool)
        grade_documents = create_grade_documents_node(grader_model, debug=False)
        rewrite_question = create_rewrite_question_node(response_model)
        generate_answer = create_generate_answer_node(response_model)
        
        # 创建消息总结节点（如果启用）
        summarize_messages = None
        if config.USE_MESSAGE_SUMMARIZATION and self.summary_llm:
            from .rag_nodes import create_summarize_messages_node
            summarize_messages = create_summarize_messages_node(self.summary_llm)
            logger.info(f"[RAGService] 已创建消息总结节点，触发阈值: {config.MESSAGE_SUMMARIZATION_THRESHOLD} tokens，保留消息数: {config.MESSAGE_SUMMARIZATION_KEEP_MESSAGES}")

        # 创建 checkpointer（如果启用）
        checkpointer = create_checkpointer()

        graph = build_rag_graph(
            retrieve_tool=retrieve_tool,
            generate_query_or_respond_node=generate_query_or_respond,
            grade_documents_node=grade_documents,
            rewrite_question_node=rewrite_question,
            generate_answer_node=generate_answer,
            summarize_messages_node=summarize_messages,
            checkpointer=checkpointer,
        )
        return graph

    @staticmethod
    def _parse_retrieve_output(text: str) -> List[Dict]:
        """
        将工具输出的格式化文本解析为 UI 需要的 retrieved_docs。
        从工具输出中提取 rerank_score 并转换为 similarity。
        """
        if not text or "No relevant documents found." in text:
            return []
        parts = text.split("\n\n[Document ")
        docs = []
        for idx, part in enumerate(parts):
            if idx == 0:
                chunk = part
            else:
                chunk = "[Document " + part
            
            # 解析 header 和 content
            if "\n" in chunk:
                header_line, content = chunk.split("\n", 1)
            else:
                header_line = chunk
                content = ""
            
            content = content.strip()
            if not content:
                continue
            
            # 从 header 中提取元数据
            # 格式: [Document {i}] (Source: ..., Rerank_score: {value}, ...)
            import re
            metadata = {}
            similarity = None
            
            # 使用正则表达式提取 rerank_score
            # 匹配 "Rerank_score: {数字}" 或 "Rerank_score:{数字}"
            rerank_match = re.search(r'Rerank_score:\s*([+-]?\d*\.?\d+)', header_line)
            if rerank_match:
                try:
                    rerank_score = float(rerank_match.group(1))
                    metadata["rerank_score"] = rerank_score
                    
                    # 将 rerank_score 转换为 similarity (0-1 范围)
                    # Cross-Encoder 的分数通常是相关性分数，越高越相关
                    # 对于 BAAI/bge-reranker-base 等模型，分数通常在 -10 到 10 之间
                    # 使用 sigmoid 函数归一化到 0-1 范围
                    import math
                    # sigmoid: 1 / (1 + exp(-x))
                    # 为了更好的显示效果，我们可以调整 sigmoid 的缩放
                    # 使用 tanh 的变体：将分数映射到 0-1
                    similarity = 1 / (1 + math.exp(-rerank_score))
                    
                    # 确保 similarity 在 0-1 范围内
                    similarity = max(0.0, min(1.0, similarity))
                except (ValueError, TypeError) as e:
                    logger.warning(f"[解析工具输出] 无法解析 Rerank_score: {e}, header: {header_line[:100]}")
            
            # 提取其他元数据（Source, Title 等）
            source_match = re.search(r'Source:\s*([^,)]+)', header_line)
            if source_match:
                metadata["source"] = source_match.group(1).strip()
            
            title_match = re.search(r'Title:\s*([^,)]+)', header_line)
            if title_match:
                metadata["title"] = title_match.group(1).strip()
            
            docs.append(
                {
                    "chunk_id": len(docs),
                    "content": content,
                    "similarity": round(similarity, 4) if similarity is not None else None,
                    "metadata": metadata,
                }
            )
        return docs

    def _query_langgraph(self, user_id: int, question: str, thread_id: Optional[str] = None) -> Dict:
        """
        LangGraph RAG 查询（非流式），返回与现有接口兼容的结果字典。
        
        重要说明：
        - retry_count 是单次请求内的控制参数，用于控制文档检索重试次数（最多 3 次）
        - 每次新用户请求时，retry_count 必须从 0 开始
        - checkpoint 会自动恢复历史 messages，但 retry_count 会被新值覆盖
        
        Args:
            user_id: 用户 ID
            question: 用户问题
            thread_id: 可选的 thread_id，用于多轮对话（checkpoint）
        """
        start_time = time.time()
        token_counter.reset()

        graph = self._build_langgraph_graph(user_id)
        
        # 每次新请求时，明确重置所有单次请求相关的状态字段
        initial_state = {
            "messages": [HumanMessage(content=question)],  # 新消息会被 add_messages reducer 追加到历史消息中
            "retry_count": 0,  # 每次新请求都重置为 0（单次请求内的重试计数）
            "current_query": question,  # 当前查询，每次新请求都更新
            "no_relevant_found": False,  # 每次新请求都重置为 False
        }

        # 配置 checkpoint
        graph_config = None
        if config.USE_CHECKPOINT:
            if not thread_id:
                # 为单次查询生成临时 thread_id
                thread_id = f"temp_{user_id}_{uuid.uuid4().hex[:8]}"
            graph_config = {"configurable": {"thread_id": thread_id}}
            logger.debug(f"[RAGService] 使用 thread_id: {thread_id}，retry_count 将从 0 开始（覆盖 checkpoint 中的旧值）")
        elif thread_id:
            # 如果提供了 thread_id 但未启用 checkpoint，仍然使用（兼容性）
            graph_config = {"configurable": {"thread_id": thread_id}}

        final_state = graph.invoke(initial_state, config=graph_config)
        messages = final_state.get("messages", []) if isinstance(final_state, dict) else []

        answer = ""
        retrieved_docs: List[Dict] = []
        tool_text = ""
        for m in messages:
            if isinstance(m, ToolMessage):
                tool_text = str(getattr(m, "content", "") or "")
        if tool_text:
            retrieved_docs = self._parse_retrieve_output(tool_text)

        if messages:
            last = messages[-1]
            answer = str(getattr(last, "content", "") or "")

        elapsed_time = time.time() - start_time

        thinking_process = [
            {"step": 1, "action": "分析问题", "description": "进入 LangGraph RAG 工作流", "details": f"问题长度: {len(question)} 字符"},
            {"step": 2, "action": "检索与评估", "description": "工具检索 + 文档相关性评估 + 可能重写", "details": f"检索到 {len(retrieved_docs)} 条内容（解析自工具输出）"},
            {"step": 3, "action": "生成答案", "description": "基于检索上下文生成回答", "details": f"回答长度: {len(answer)} 字符"},
            {"step": 4, "action": "完成", "description": "回答生成完成", "details": f"耗时: {elapsed_time:.2f} 秒"},
        ]

        tokens_used = token_counter.total_stats.get("total_tokens", 0) or (len(question) // 4 + len(answer) // 4)

        return {
            "answer": answer,
            "retrieved_docs": retrieved_docs,
            "thinking_process": thinking_process,
            "elapsed_time": elapsed_time,
            "tokens_used": tokens_used,
            "fallback_mode": False,
        }

    def _query_langgraph_stream(self, user_id: int, question: str, thread_id: Optional[str] = None) -> Generator[Dict, None, None]:
        """
        LangGraph RAG 流式查询，使用 graph.stream() 实现真正的流式输出。
        
        重要说明：
        - retry_count 是单次请求内的控制参数，用于控制文档检索重试次数（最多 3 次）
        - 每次新用户请求时，retry_count 必须从 0 开始
        - checkpoint 会自动恢复历史 messages，但 retry_count 会被新值覆盖
        - SummarizationMiddleware 会在消息超过阈值时自动总结
        
        Args:
            user_id: 用户 ID
            question: 用户问题
            thread_id: 可选的 thread_id，用于多轮对话（checkpoint）
        """
        start_time = time.time()
        token_counter.reset()

        graph = self._build_langgraph_graph(user_id)
        
        # 每次新请求时，明确重置所有单次请求相关的状态字段
        # 这些字段不应该跨请求保持，每次新请求都从初始值开始
        initial_state = {
            "messages": [HumanMessage(content=question)],  # 新消息会被 add_messages reducer 追加到历史消息中
            "retry_count": 0,  # 每次新请求都重置为 0（单次请求内的重试计数）
            "current_query": question,  # 当前查询，每次新请求都更新
            "no_relevant_found": False,  # 每次新请求都重置为 False
        }

        # 配置 checkpoint
        graph_config = None
        if config.USE_CHECKPOINT:
            if not thread_id:
                # 为单次查询生成临时 thread_id
                thread_id = f"temp_{user_id}_{uuid.uuid4().hex[:8]}"
            
            # 关键：使用 config 参数明确指定要重置的字段
            # LangGraph 会将 initial_state 中的值应用到状态中
            # 对于没有 reducer 的字段（如 retry_count），新值会覆盖 checkpoint 中的旧值
            graph_config = {"configurable": {"thread_id": thread_id}}
            logger.debug(f"[RAGService] 使用 thread_id: {thread_id}，retry_count 将从 0 开始（覆盖 checkpoint 中的旧值）")
        elif thread_id:
            # 如果提供了 thread_id 但未启用 checkpoint，仍然使用（兼容性）
            graph_config = {"configurable": {"thread_id": thread_id}}

        # 用于收集最终结果
        final_answer = ""
        retrieved_docs: List[Dict] = []
        tool_text = ""
        thinking_steps = []
        current_step = 1

        # 流式处理 graph 输出
        logger.info(f"[RAGService] 开始 LangGraph 流式查询，thread_id={thread_id}")
        logger.info(f"[RAGService] 初始状态 - messages 数量: {len(initial_state['messages'])}")
        for msg in initial_state['messages']:
            logger.info(f"  初始消息: {type(msg).__name__} - {str(msg.content)[:100]}...")
        
        # 如果使用 checkpoint，尝试获取历史消息（用于调试）
        if config.USE_CHECKPOINT and thread_id:
            try:
                # 尝试获取历史状态（仅用于调试，不修改）
                from langgraph.checkpoint.base import Checkpoint
                # 注意：这里只是示例，实际 API 可能不同
                logger.debug(f"[RAGService] 使用 checkpoint，thread_id={thread_id}")
            except Exception:
                pass
        
        for chunk in graph.stream(initial_state, config=graph_config):
            for node_name, node_update in chunk.items():
                logger.info(f"[RAGService] LangGraph 节点更新: {node_name}")
                # 处理不同节点的更新
                if node_name == "generate_query_or_respond":
                    thinking_steps.append({
                        "step": current_step,
                        "action": "分析问题",
                        "description": "生成查询或判断是否需要检索",
                        "details": " 判断是否文档检索 "
                    })
                    current_step += 1
                
                elif node_name == "retrieve":
                    # 提取工具返回的文档
                    if "messages" in node_update:
                        for msg in node_update["messages"]:
                            if isinstance(msg, ToolMessage):
                                tool_text = str(getattr(msg, "content", "") or "")
                                if tool_text:
                                    retrieved_docs = self._parse_retrieve_output(tool_text)
                    
                    thinking_steps.append({
                        "step": current_step,
                        "action": "文档检索",
                        "description": f"检索到 {len(retrieved_docs)} 个相关段落",
                        "details": "工具检索完成"
                    })
                    current_step += 1
                
                elif node_name == "grade_documents":
                    thinking_steps.append({
                        "step": current_step,
                        "action": "评估文档相关性",
                        "description": "判断检索到的文档是否相关",
                        "details": "文档相关性评估"
                    })
                    current_step += 1
                
                elif node_name == "rewrite_question":
                    thinking_steps.append({
                        "step": current_step,
                        "action": "重写问题",
                        "description": "优化查询以提高检索效果",
                        "details": "问题重写"
                    })
                    current_step += 1
                
                elif node_name == "generate_answer":
                    # generate_answer 节点内部已经实现了流式输出
                    # 但这里我们只能获取节点完成后的最终消息
                    if "messages" in node_update:
                        for msg in node_update["messages"]:
                            if hasattr(msg, "content"):
                                content = str(getattr(msg, "content", "") or "")
                                if content and not content.startswith("用户问题:"):  # 排除重试时的提示
                                    final_answer = content
                    
                    # 由于节点内部流式输出无法在这里捕获，我们采用折中方案：
                    # 如果答案已生成，直接 yield 完整答案（后续可以优化为真正的流式）
                    if final_answer:
                        thinking_steps.append({
                            "step": current_step,
                            "action": "生成答案",
                            "description": "基于检索上下文生成回答",
                            "details": f"回答长度: {len(final_answer)} 字符"
                        })
                        current_step += 1

        elapsed_time = time.time() - start_time

        # 构建完整的 thinking_process
        if not thinking_steps:
            thinking_steps = [
                {"step": 1, "action": "分析问题", "description": "进入 LangGraph RAG 工作流", "details": f"问题长度: {len(question)} 字符"},
                {"step": 2, "action": "检索与评估", "description": "工具检索 + 文档相关性评估", "details": f"检索到 {len(retrieved_docs)} 条内容"},
                {"step": 3, "action": "生成答案", "description": "基于检索上下文生成回答", "details": f"回答长度: {len(final_answer)} 字符"},
            ]
        
        thinking_steps.append({
            "step": len(thinking_steps) + 1,
            "action": "完成",
            "description": "回答生成完成",
            "details": f"耗时: {elapsed_time:.2f} 秒"
        })

        tokens_used = token_counter.total_stats.get("total_tokens", 0) or (len(question) // 4 + len(final_answer) // 4)

        # Yield 思考过程
        yield {"type": "thinking", "thinking_process": thinking_steps}

        # Yield 答案（由于节点内部流式无法捕获，这里采用分片方式）
        # 注意：这是折中方案，真正的流式需要修改节点实现
        if final_answer:
            step = 50
            for i in range(0, len(final_answer), step):
                yield {"type": "chunk", "content": final_answer[i : i + step]}

        # 打印完整的 Token 统计
        logger.info("\n" + "=" * 80)
        logger.info("📊 完整 Token 使用统计")
        logger.info("=" * 80)
        
        # 总体统计
        total_stats = token_counter.total_stats
        logger.info(f"\n【总体统计】")
        logger.info(f"  总调用次数: {total_stats.get('call_count', 0)}")
        logger.info(f"  总输入 Token: {int(total_stats.get('input_tokens', 0)):,}")
        logger.info(f"  总输出 Token: {int(total_stats.get('output_tokens', 0)):,}")
        logger.info(f"  总 Token: {int(total_stats.get('total_tokens', 0)):,}")
        
        # 按节点统计
        if token_counter.node_stats:
            logger.info(f"\n【按节点统计】")
            for node_name, stats in token_counter.node_stats.items():
                logger.info(f"  {node_name}:")
                logger.info(f"    调用次数: {stats.get('call_count', 0)}")
                logger.info(f"    输入 Token: {int(stats.get('input_tokens', 0)):,}")
                logger.info(f"    输出 Token: {int(stats.get('output_tokens', 0)):,}")
                logger.info(f"    总 Token: {int(stats.get('total_tokens', 0)):,}")
        
        # 按模型统计
        if token_counter.model_stats:
            logger.info(f"\n【按模型统计】")
            for model_name, stats in token_counter.model_stats.items():
                logger.info(f"  {model_name}:")
                logger.info(f"    调用次数: {stats.get('call_count', 0)}")
                logger.info(f"    输入 Token: {int(stats.get('input_tokens', 0)):,}")
                logger.info(f"    输出 Token: {int(stats.get('output_tokens', 0)):,}")
                logger.info(f"    总 Token: {int(stats.get('total_tokens', 0)):,}")
        
        logger.info("=" * 80 + "\n")
        
        # Yield 完成信息
        yield {
            "type": "complete",
            "answer": final_answer,
            "retrieved_docs": retrieved_docs,
            "thinking_process": thinking_steps,
            "elapsed_time": elapsed_time,
            "tokens_used": tokens_used,
            "fallback_mode": False,
        }
    
    def query(self, user_id: int, question: str, k: int = None, thread_id: Optional[str] = None) -> Dict:
        """
        执行 RAG 查询
        
        Args:
            user_id: 用户 ID
            question: 用户问题
            k: 检索数量
            thread_id: 可选的 thread_id，用于多轮对话（checkpoint）
        
        Returns:
            查询结果字典：
            {
                'answer': str,
                'retrieved_docs': List[Dict],
                'thinking_process': List[Dict],
                'elapsed_time': float,
                'tokens_used': int
            }
        """
        # LangGraph 路径（可选）
        if config.USE_LANGGRAPH_RAG:
            return self._query_langgraph(user_id, question, thread_id=thread_id)

        start_time = time.time()
        
        # 1. 向量检索
        thinking_process = []
        thinking_process.append({
            'step': 1,
            'action': '分析问题',
            'description': f'识别问题类型并提取关键词',
            'details': f'问题长度: {len(question)} 字符'
        })
        
        docs_with_scores = self.vector_service.search_with_score(user_id, question, k=k)
        
        # 判断是否需要降级到直接回答
        should_fallback = False
        fallback_reason = ""
        
        if not docs_with_scores:
            # 情况 A：没有检索到文档
            should_fallback = True
            fallback_reason = "未找到相关文档"
        elif config.RAG_FALLBACK_ENABLED:
            # 情况 B：检查相似度阈值
            max_similarity = max([max(0, 1 - score) for _, score in docs_with_scores])
            if max_similarity < config.RAG_SIMILARITY_THRESHOLD:
                should_fallback = True
                fallback_reason = f"相似度太低（最高相似度: {max_similarity:.2f}）"
        
        if should_fallback:
            # 使用直接回答模式
            thinking_process.append({
                'step': 2,
                'action': '降级到直接回答',
                'description': fallback_reason,
                'details': '使用大模型直接回答，不依赖知识库'
            })
            
            thinking_process.append({
                'step': 3,
                'action': '生成答案',
                'description': '使用大模型直接回答',
                'details': '不依赖知识库内容'
            })
            
            # 使用直接回答 Chain
            direct_chain = self.direct_prompt | self.llm | StrOutputParser()
            answer = direct_chain.invoke({"question": question})
            
            elapsed_time = time.time() - start_time
            
            thinking_process.append({
                'step': 4,
                'action': '完成',
                'description': f'回答生成完成',
                'details': f'耗时: {elapsed_time:.2f} 秒'
            })
            
            # 估算 Token 消耗（直接回答没有上下文）
            estimated_tokens = len(question) // 4 + len(answer) // 4
            
            return {
                'answer': answer,
                'retrieved_docs': [],
                'thinking_process': thinking_process,
                'elapsed_time': elapsed_time,
                'tokens_used': estimated_tokens,
                'fallback_mode': True,
                'fallback_reason': fallback_reason
            }
        
        # 2. 处理检索结果（RAG 模式）
        retrieved_docs = []
        context_parts = []
        
        for i, (doc, score) in enumerate(docs_with_scores):
            # 转换评分为相似度（Chroma 使用距离，越小越相似）
            similarity = max(0, 1 - score)  # 简单转换
            
            retrieved_docs.append({
                'chunk_id': i,
                'content': doc.page_content,
                'similarity': round(similarity, 2),
                'metadata': doc.metadata
            })
            
            context_parts.append(f"[文档片段 {i+1}]\n{doc.page_content}")
        
        context = "\n\n".join(context_parts)
        
        avg_similarity = sum([d['similarity'] for d in retrieved_docs]) / len(retrieved_docs)
        thinking_process.append({
            'step': 2,
            'action': '文档检索',
            'description': f'检索到 {len(retrieved_docs)} 个相关段落',
            'details': f'平均相似度: {avg_similarity:.2f}'
        })
        
        # 3. 构造 Prompt 并调用 LLM
        thinking_process.append({
            'step': 3,
            'action': '生成答案',
            'description': '基于检索结果生成回答',
            'details': f'上下文长度: {len(context)} 字符'
        })
        
        # 使用 LangChain RAG Chain
        rag_chain = (
            {"context": lambda x: context, "question": RunnablePassthrough()}
            | self.prompt
            | self.llm
            | StrOutputParser()
        )
        
        answer = rag_chain.invoke(question)
        
        elapsed_time = time.time() - start_time
        
        thinking_process.append({
            'step': 4,
            'action': '完成',
            'description': f'回答生成完成',
            'details': f'耗时: {elapsed_time:.2f} 秒'
        })
        
        # TODO: 计算实际 Token 消耗
        estimated_tokens = len(context) // 4 + len(question) // 4 + len(answer) // 4
        
        return {
            'answer': answer,
            'retrieved_docs': retrieved_docs,
            'thinking_process': thinking_process,
            'elapsed_time': elapsed_time,
            'tokens_used': estimated_tokens,
            'fallback_mode': False
        }
    
    def query_stream(self, user_id: int, question: str, k: int = None, thread_id: Optional[str] = None) -> Generator[Dict, None, None]:
        """
        流式执行 RAG 查询
        
        Args:
            user_id: 用户 ID
            question: 用户问题
            k: 检索数量
        
        Yields:
            字典，包含不同类型的信息：
            - type='thinking': 思考过程信息
              {
                  'type': 'thinking',
                  'thinking_process': List[Dict]
              }
            - type='chunk': 答案片段
              {
                  'type': 'chunk',
                  'content': str  # 增量内容
              }
            - type='complete': 完成信息（最后一条）
              {
                  'type': 'complete',
                  'answer': str,  # 完整答案
                  'retrieved_docs': List[Dict],
                  'thinking_process': List[Dict],
                  'elapsed_time': float,
                  'tokens_used': int
              }
        """
        # LangGraph 路径（可选）：当前为了保持接口兼容，采用“先求完整答案，再分片输出”的方式
        # LangGraph 路径（可选）：使用真正的流式输出
        if config.USE_LANGGRAPH_RAG:
            for response in self._query_langgraph_stream(user_id, question, thread_id=thread_id):
                yield response
            return

        start_time = time.time()
        
        # 1. 向量检索
        thinking_process = []
        thinking_process.append({
            'step': 1,
            'action': '分析问题',
            'description': f'识别问题类型并提取关键词',
            'details': f'问题长度: {len(question)} 字符'
        })
        
        docs_with_scores = self.vector_service.search_with_score(user_id, question, k=k)
        
        # 判断是否需要降级到直接回答
        should_fallback = False
        fallback_reason = ""
        
        if not docs_with_scores:
            # 情况 A：没有检索到文档
            should_fallback = True
            fallback_reason = "未找到相关文档"
        elif config.RAG_FALLBACK_ENABLED:
            # 情况 B：检查相似度阈值
            max_similarity = max([max(0, 1 - score) for _, score in docs_with_scores])
            if max_similarity < config.RAG_SIMILARITY_THRESHOLD:
                should_fallback = True
                fallback_reason = f"相似度太低（最高相似度: {max_similarity:.2f}）"
        
        if should_fallback:
            # 使用直接回答模式（流式）
            thinking_process.append({
                'step': 2,
                'action': '降级到直接回答',
                'description': fallback_reason,
                'details': '使用大模型直接回答，不依赖知识库'
            })
            
            thinking_process.append({
                'step': 3,
                'action': '生成答案',
                'description': '使用大模型直接回答',
                'details': '不依赖知识库内容'
            })
            
            # 先 yield 思考过程
            yield {
                'type': 'thinking',
                'thinking_process': thinking_process
            }
            
            # 流式生成直接回答
            direct_chain = self.direct_prompt | self.llm | StrOutputParser()
            full_answer = ""
            for chunk in direct_chain.stream({"question": question}):
                full_answer += chunk
                yield {
                    'type': 'chunk',
                    'content': chunk
                }
            
            elapsed_time = time.time() - start_time
            
            thinking_process.append({
                'step': 4,
                'action': '完成',
                'description': f'回答生成完成',
                'details': f'耗时: {elapsed_time:.2f} 秒'
            })
            
            # 估算 Token 消耗（直接回答没有上下文）
            estimated_tokens = len(question) // 4 + len(full_answer) // 4
            
            # 最后 yield 完整结果
            yield {
                'type': 'complete',
                'answer': full_answer,
                'retrieved_docs': [],
                'thinking_process': thinking_process,
                'elapsed_time': elapsed_time,
                'tokens_used': estimated_tokens,
                'fallback_mode': True,
                'fallback_reason': fallback_reason
            }
            return
        
        # 2. 处理检索结果（RAG 模式）
        retrieved_docs = []
        context_parts = []
        
        for i, (doc, score) in enumerate(docs_with_scores):
            # 转换评分为相似度（Chroma 使用距离，越小越相似）
            similarity = max(0, 1 - score)  # 简单转换
            
            retrieved_docs.append({
                'chunk_id': i,
                'content': doc.page_content,
                'similarity': round(similarity, 2),
                'metadata': doc.metadata
            })
            
            context_parts.append(f"[文档片段 {i+1}]\n{doc.page_content}")
        
        context = "\n\n".join(context_parts)
        
        avg_similarity = sum([d['similarity'] for d in retrieved_docs]) / len(retrieved_docs)
        thinking_process.append({
            'step': 2,
            'action': '文档检索',
            'description': f'检索到 {len(retrieved_docs)} 个相关段落',
            'details': f'平均相似度: {avg_similarity:.2f}'
        })
        
        # 3. 构造 Prompt 并调用 LLM（流式）
        thinking_process.append({
            'step': 3,
            'action': '生成答案',
            'description': '基于检索结果生成回答',
            'details': f'上下文长度: {len(context)} 字符'
        })
        
        # 先 yield 思考过程
        yield {
            'type': 'thinking',
            'thinking_process': thinking_process
        }
        
        # 使用 LangChain RAG Chain（流式）
        rag_chain = (
            {"context": lambda x: context, "question": RunnablePassthrough()}
            | self.prompt
            | self.llm
            | StrOutputParser()
        )
        
        # 流式生成答案
        full_answer = ""
        for chunk in rag_chain.stream(question):
            full_answer += chunk
            yield {
                'type': 'chunk',
                'content': chunk
            }
        
        elapsed_time = time.time() - start_time
        
        thinking_process.append({
            'step': 4,
            'action': '完成',
            'description': f'回答生成完成',
            'details': f'耗时: {elapsed_time:.2f} 秒'
        })
        
        # TODO: 计算实际 Token 消耗
        estimated_tokens = len(context) // 4 + len(question) // 4 + len(full_answer) // 4
        
        # 最后 yield 完整结果
        yield {
            'type': 'complete',
            'answer': full_answer,
            'retrieved_docs': retrieved_docs,
            'thinking_process': thinking_process,
            'elapsed_time': elapsed_time,
            'tokens_used': estimated_tokens,
            'fallback_mode': False
        }
    
    def format_docs(self, docs) -> str:
        """格式化文档列表为字符串"""
        return "\n\n".join(doc.page_content for doc in docs)


# 全局 RAG 服务实例
_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """获取全局 RAG 服务实例（单例）"""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service

