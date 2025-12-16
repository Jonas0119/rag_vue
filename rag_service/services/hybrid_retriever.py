"""
Hybrid Retriever 实现
结合向量检索与 BM25（RRF 融合）
"""

import logging
from typing import List, Optional, Dict
from collections import defaultdict

from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever

from rag_service.services.vector_store_service import get_vector_store_service
from rag_service.services.vector_strategies import ChromaStrategy

logger = logging.getLogger(__name__)

# 中文分词支持
try:
    import jieba
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False
    logger.warning("[HybridRetriever] jieba 未安装，BM25 将使用默认分词（对中文不友好）")


def jieba_tokenizer(text: str) -> List[str]:
    """
    使用 jieba 对中文文本进行分词
    
    Args:
        text: 待分词的文本
        
    Returns:
        分词后的词列表
    """
    if not JIEBA_AVAILABLE:
        # 如果没有 jieba，回退到简单的字符分割（对中文不友好）
        return text.split()
    
    # 使用 jieba 进行精确模式分词
    return jieba.lcut(text, cut_all=False)


def reciprocal_rank_fusion(result_lists: List[List[Document]], k: int = 20, c: int = 60) -> List[Document]:
    """
    简单实现 RRF，将多个检索结果融合。
    Args:
        result_lists: List[List[Document]]
        k: 截取每路结果的数量
        c: 平滑因子
    Returns:
        融合后的排序文档列表
    """
    scores = defaultdict(float)
    doc_map: Dict[str, Document] = {}

    for results in result_lists:
        for rank, doc in enumerate(results[:k]):
            key = (doc.page_content, str(doc.metadata))
            scores[key] += 1.0 / (c + rank + 1)
            # 保留文档对象
            if key not in doc_map:
                doc_map[key] = doc

    # 根据得分排序
    sorted_items = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    fused_docs = [doc_map[key] for key, _ in sorted_items]
    return fused_docs[:k]


class HybridRetriever:
    """
    结合向量检索与 BM25 的检索器。
    注意：BM25 只在本地 Chroma 模式下构建，云模式下回退为纯向量检索。
    """

    def __init__(self, user_id: int, top_k: int = 20):
        self.user_id = user_id
        self.top_k = top_k
        self.vector_service = get_vector_store_service()
        self._bm25_retriever: Optional[BM25Retriever] = None
        self._parent_map: Optional[Dict[str, Document]] = None  # 由上层注入（Parent-Child 模式）
        self._bm25_build_attempted = False  # 标记是否已尝试构建 BM25
        # 不再在 __init__ 中立即构建 BM25，延迟到第一次 invoke 时构建
        # 原因：VectorStoreService 的 strategy 是异步加载的，初始化时可能还未加载完成

    def _build_bm25_if_possible(self):
        """
        仅在本地 Chroma 模式下构建 BM25。
        注意：会等待 strategy 加载完成。
        """
        try:
            # 等待 strategy 加载完成
            if not self.vector_service.is_embeddings_ready():
                logger.info("[HybridRetriever] 等待 Embedding 模型和 strategy 加载完成...")
                # 等待最多 60 秒
                if not self.vector_service._ensure_embeddings_loaded(timeout=60.0):
                    logger.warning("[HybridRetriever] Embedding 模型加载超时，跳过 BM25 构建")
                    return
            
            strategy = self.vector_service.strategy
            if strategy is None:
                logger.warning("[HybridRetriever] strategy 为 None，跳过 BM25 构建")
                return
            
            # 仅针对 Chroma 策略构建 BM25
            strategy_type = type(strategy)
            strategy_type_name = strategy_type.__name__
            strategy_module = strategy_type.__module__
            
            # 检查是否是 ChromaStrategy 实例
            # 使用类型名称和模块名双重检查，避免导入问题
            is_chroma = isinstance(strategy, ChromaStrategy)
            
            if not is_chroma:
                logger.info(
                    "[HybridRetriever] 非 Chroma 策略（类型: %s，模块: %s），跳过 BM25 构建",
                    strategy_type_name,
                    strategy_module
                )
                logger.debug(
                    "[HybridRetriever] isinstance 检查结果: %s, ChromaStrategy 模块: %s",
                    is_chroma,
                    ChromaStrategy.__module__
                )
                return

            vectorstore = strategy.get_vector_store(self.user_id)
            # 从 Chroma 取出所有文档（按 user_id 过滤）
            raw = vectorstore._collection.get(
                where={"user_id": self.user_id},
                include=["documents", "metadatas"],
            )
            docs = []
            for content, meta in zip(raw.get("documents", []), raw.get("metadatas", [])):
                if not content:
                    continue
                docs.append(Document(page_content=content, metadata=meta or {}))

            if not docs:
                logger.info("[HybridRetriever] 未找到可用于 BM25 的文档，跳过构建")
                return

            # 使用 jieba 分词器（如果可用）以支持中文
            preprocess_func = jieba_tokenizer if JIEBA_AVAILABLE else None
            bm25 = BM25Retriever.from_documents(
                docs,
                preprocess_func=preprocess_func
            )
            bm25.k = self.top_k
            self._bm25_retriever = bm25
            logger.info(
                "[HybridRetriever] BM25 构建完成，文档数=%d，分词器=%s",
                len(docs),
                "jieba" if JIEBA_AVAILABLE else "默认"
            )
        except Exception as e:
            # 检查是否是 rank_bm25 导入错误
            error_msg = str(e)
            if "rank_bm25" in error_msg or "Could not import rank_bm25" in error_msg:
                logger.warning("[HybridRetriever] rank_bm25 未安装，请运行: poetry add rank-bm25 或 pip install rank-bm25")
                logger.warning("[HybridRetriever] 回退为纯向量检索")
            else:
                logger.warning("[HybridRetriever] 构建 BM25 失败，回退为纯向量检索: %s", e)
            self._bm25_retriever = None

    def invoke(self, query: str) -> List[Document]:
        """
        LangGraph/ToolNode 期望的检索接口。
        """
        # 延迟构建 BM25（如果尚未构建且 strategy 已加载）
        if not self._bm25_build_attempted:
            self._build_bm25_if_possible()
            self._bm25_build_attempted = True
        
        # 向量检索
        vector_retriever = self.vector_service.get_retriever(self.user_id, k=self.top_k)
        vector_docs = vector_retriever.invoke(query)[: self.top_k]

        # BM25 检索（如果可用）
        bm25_docs: List[Document] = []
        if self._bm25_retriever:
            try:
                bm25_docs = self._bm25_retriever.invoke(query)[: self.top_k]
            except Exception as e:
                logger.warning("[HybridRetriever] BM25 检索失败，忽略 BM25: %s", e)

        # 如果没有 BM25，直接返回向量检索结果
        if not bm25_docs:
            return vector_docs

        # RRF 融合
        return reciprocal_rank_fusion([bm25_docs, vector_docs], k=self.top_k)

    # Parent-Child 支持：供工具读取父文档映射
    def get_parent_map(self) -> Optional[Dict[str, Document]]:
        return self._parent_map

    def set_parent_map(self, parent_map: Dict[str, Document]):
        self._parent_map = parent_map


