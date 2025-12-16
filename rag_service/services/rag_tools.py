"""
工具定义模块
定义 RAG 系统中使用的检索工具
"""

import logging
from typing import Optional, Dict

from langchain.tools import tool
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document

from rag_service.services.reranker import CrossEncoderReranker

logger = logging.getLogger(__name__)


def create_retrieve_tool(
    retriever: BaseRetriever,
    reranker: Optional[CrossEncoderReranker] = None,
    top_k: int = 20,
    top_n: int = 3,
    rerank_score_threshold: Optional[float] = None,
):
    """
    创建检索工具（支持 Parent-Child 策略和 Rerank 阈值过滤）
    
    Args:
        retriever: 向量存储的 retriever 对象（如果是 Parent-Child 模式，应包含 parent_map）
        reranker: Cross-Encoder 重排序器
        top_k: 初始检索的候选数量（用于 rerank）
        top_n: rerank 后返回的文档数量上限
        rerank_score_threshold: Rerank 分数阈值，低于此分数的文档将被过滤（None 表示不过滤）
        
    Returns:
        装饰后的工具函数（工具名自动使用函数名 "retrieve_documents"）
    """
    # 检查是否使用 Parent-Child 策略
    parent_map: Optional[Dict[str, Document]] = None
    if hasattr(retriever, 'get_parent_map'):
        parent_map = retriever.get_parent_map()
    
    @tool
    def retrieve_documents(query: str) -> str:
        """检索文档并返回格式化结果。"""
        logger.info("=" * 80)
        logger.info(f"[LangGraph工具] retrieve_documents: 开始执行")
        logger.info(f"[输入] 查询: {query}")
        # 使用 retriever 的 invoke 方法获取相关文档 (Hybrid + RRF, Top-K)
        # 如果是 Parent-Child 模式，这里返回的是子文档
        child_docs = retriever.invoke(query)
        logger.info(f"[输出] 检索到 {len(child_docs)} 个子文档")
        
        if not child_docs:
            return "No relevant documents found."
        
        # Parent-Child 策略：将子文档映射到父文档
        if parent_map:
            # 收集所有唯一的父文档 ID
            parent_ids = set()
            for child_doc in child_docs:
                parent_id = child_doc.metadata.get("parent_id")
                if parent_id and parent_id in parent_map:
                    parent_ids.add(parent_id)
            
            # 获取对应的父文档
            parent_docs = [parent_map[pid] for pid in parent_ids if pid in parent_map]
            
            # 如果有 reranker，对父文档进行重排序（应用阈值过滤）
            if reranker:
                logger.info(f"[LangGraph工具] retrieve_documents: 使用 Reranker 重排序 {len(parent_docs)} 个父文档")
                parent_docs = reranker.rerank(
                    query, 
                    parent_docs, 
                    top_n=top_n,
                    score_threshold=rerank_score_threshold
                )
                logger.info(f"[LangGraph工具] retrieve_documents: Rerank 后剩余 {len(parent_docs)} 个父文档")
            else:
                parent_docs = parent_docs[:top_n]
            
            # 使用父文档作为最终结果
            docs = parent_docs
        else:
            # 传统模式：直接使用检索到的文档
            if reranker:
                logger.info(f"[LangGraph工具] retrieve_documents: 使用 Reranker 重排序 {len(child_docs)} 个文档")
                docs = reranker.rerank(
                    query, 
                    child_docs, 
                    top_n=top_n,
                    score_threshold=rerank_score_threshold
                )
                logger.info(f"[LangGraph工具] retrieve_documents: Rerank 后剩余 {len(docs)} 个文档")
            else:
                docs = child_docs[:top_n]
        
        logger.info(f"[输出] 最终返回 {len(docs)} 个文档")
        
        # 格式化输出：合并文档内容，包含元数据信息与 rerank 分数
        # 如果返回 0 个文档（由于阈值过滤），grade_documents 会返回 "no"，触发 rewrite_question
        if not docs:
            return "No relevant documents found."
        
        result_parts = []
        for i, doc in enumerate(docs, 1):
            content = doc.page_content.strip()
            if content:
                # 构建文档头部，包含元数据
                doc_header = f"[Document {i}]"
                
                # 添加元数据信息（来源 URL、标题等）
                metadata_parts = []
                if doc.metadata:
                    # 提取来源 URL
                    source = doc.metadata.get("source", "")
                    if source:
                        metadata_parts.append(f"Source: {source}")
                    
                    # 提取标题
                    title = doc.metadata.get("title", "")
                    if title:
                        metadata_parts.append(f"Title: {title}")
                    
                    # 其他有用的元数据
                    for key in ["author", "date", "page", "rerank_score"]:
                        if key in doc.metadata and doc.metadata[key] is not None:
                            metadata_parts.append(f"{key.capitalize()}: {doc.metadata[key]}")
                    
                    # 如果是 Parent-Child 模式，标记文档类型
                    if doc.metadata.get("doc_type") == "parent":
                        metadata_parts.append("Type: Parent (完整上下文)")
                
                # 组合文档信息
                if metadata_parts:
                    doc_header += f" ({', '.join(metadata_parts)})"
                
                result_parts.append(f"{doc_header}\n{content}")
        
        result_text = "\n\n".join(result_parts)
        logger.info(f"[输出] 格式化结果长度: {len(result_text)} 字符")
        logger.info(f"[输出] 结果预览: {result_text[:300]}...")
        logger.info("[LangGraph工具] retrieve_documents: 完成")
        logger.info("=" * 80)
        
        return result_text
    
    return retrieve_documents


