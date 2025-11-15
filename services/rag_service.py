"""
RAG 服务 - 检索增强生成
"""
import os
from typing import List, Dict, Optional
import time

from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from utils.config import config
from .vector_store_service import get_vector_store_service


# RAG Prompt 模板
RAG_TEMPLATE = """你是一个专业的文档分析助手。请基于以下检索到的相关内容回答问题。

相关文档内容：
{context}

用户问题：
{question}

请仔细分析文档内容，给出详细和准确的回答。如果文档中没有相关信息，请如实说明。
"""


class RAGService:
    """RAG 问答服务"""
    
    def __init__(self):
        self.vector_service = get_vector_store_service()
        self.llm = self._init_llm()
        self.prompt = ChatPromptTemplate.from_template(RAG_TEMPLATE)
    
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
    
    def query(self, user_id: int, question: str, k: int = None) -> Dict:
        """
        执行 RAG 查询
        
        Args:
            user_id: 用户 ID
            question: 用户问题
            k: 检索数量
        
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
        
        if not docs_with_scores:
            return {
                'answer': '抱歉，我在知识库中没有找到相关信息。请确保已上传相关文档。',
                'retrieved_docs': [],
                'thinking_process': thinking_process,
                'elapsed_time': time.time() - start_time,
                'tokens_used': 0
            }
        
        # 2. 处理检索结果
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
            'tokens_used': estimated_tokens
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

