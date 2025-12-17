"""
向量库策略实现
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, TYPE_CHECKING
import logging
from pathlib import Path

from langchain_core.documents import Document
from rag_service.utils.config import config

logger = logging.getLogger(__name__)

# 类型检查时的导入（用于类型注解）
if TYPE_CHECKING:
    from langchain_chroma import Chroma
    from langchain_pinecone import PineconeVectorStore

# Chroma 相关导入（可选，本地开发使用）
try:
    from langchain_chroma import Chroma  # type: ignore[import]
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    Chroma = None  # type: ignore[assignment, misc]

# Pinecone 相关导入（云模式）
try:
    from pinecone import Pinecone, ServerlessSpec
    from langchain_pinecone import PineconeVectorStore
    PINECONE_AVAILABLE = True
except ImportError:
    PINECONE_AVAILABLE = False
    Pinecone = None  # type: ignore[assignment, misc]
    ServerlessSpec = None  # type: ignore[assignment, misc]
    PineconeVectorStore = None  # type: ignore[assignment, misc]


class VectorStoreStrategy(ABC):
    """向量库策略基类"""
    
    def __init__(self, embeddings: Any):
        self.embeddings = embeddings

    @abstractmethod
    def get_vector_store(self, user_id: int) -> Any:
        """获取向量库实例"""
        pass

    @abstractmethod
    def add_documents(self, user_id: int, documents: List[Document]) -> List[str]:
        """添加文档"""
        pass

    @abstractmethod
    def delete_documents(self, user_id: int, doc_id: str):
        """删除文档"""
        pass

    @abstractmethod
    def search(self, user_id: int, query: str, k: int, filter_args: Optional[Dict] = None) -> List[Document]:
        """搜索文档"""
        pass

    @abstractmethod
    def search_with_score(self, user_id: int, query: str, k: int, filter_args: Optional[Dict] = None) -> List[tuple]:
        """带分数的搜索"""
        pass
    
    @abstractmethod
    def get_document_count(self, user_id: int) -> int:
        """获取文档数量"""
        pass
    
    @abstractmethod
    def clear_cache(self, user_id: Optional[int] = None):
        """清除缓存"""
        pass


class ChromaStrategy(VectorStoreStrategy):
    """Chroma 策略"""
    
    def __init__(self, embeddings: Any):
        if not CHROMA_AVAILABLE:
            raise ImportError(
                "未安装 langchain-chroma/chromadb，无法使用本地 Chroma 向量库。\n"
                "在 Vercel 云部署中，请使用 VECTOR_DB_MODE=cloud（Pinecone），"
                "本地开发需要 Chroma 时再安装相关依赖。"
            )
        super().__init__(embeddings)
        self._cache = {}

    def _get_collection_name(self, user_id: int) -> str:
        return f"user_{user_id}_docs"
    
    def _get_persist_directory(self, user_id: int) -> str:
        return f"{config.CHROMA_DB_DIR}/user_{user_id}_collection"

    def get_vector_store(self, user_id: int) -> Any:  # 返回类型: Chroma
        cache_key = f"chroma_{user_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        collection_name = self._get_collection_name(user_id)
        persist_directory = self._get_persist_directory(user_id)
        
        Path(persist_directory).mkdir(parents=True, exist_ok=True)
        
        vectorstore = Chroma(
            collection_name=collection_name,
            embedding_function=self.embeddings,
            persist_directory=persist_directory
        )
        
        self._cache[cache_key] = vectorstore
        return vectorstore

    def add_documents(self, user_id: int, documents: List[Document]) -> List[str]:
        vectorstore = self.get_vector_store(user_id)
        return vectorstore.add_documents(documents)

    def delete_documents(self, user_id: int, doc_id: str):
        vectorstore = self.get_vector_store(user_id)
        results = vectorstore.get(where={"doc_id": doc_id})
        if results and results['ids']:
            vectorstore.delete(ids=results['ids'])

    def search(self, user_id: int, query: str, k: int, filter_args: Optional[Dict] = None) -> List[Document]:
        vectorstore = self.get_vector_store(user_id)
        return vectorstore.similarity_search(query, k=k, filter=filter_args)

    def search_with_score(self, user_id: int, query: str, k: int, filter_args: Optional[Dict] = None) -> List[tuple]:
        vectorstore = self.get_vector_store(user_id)
        return vectorstore.similarity_search_with_score(query, k=k, filter=filter_args)

    def get_document_count(self, user_id: int) -> int:
        try:
            vectorstore = self.get_vector_store(user_id)
            return vectorstore._collection.count()
        except Exception:
            return 0

    def clear_cache(self, user_id: Optional[int] = None):
        if user_id:
            cache_key = f"chroma_{user_id}"
            if cache_key in self._cache:
                del self._cache[cache_key]
        else:
            self._cache.clear()


class PineconeStrategy(VectorStoreStrategy):
    """Pinecone 策略"""
    
    def __init__(self, embeddings: Any):
        super().__init__(embeddings)
        self._cache = {}
        if not PINECONE_AVAILABLE:
            raise ImportError("使用 Pinecone 需要安装: pip install pinecone-client langchain-pinecone")
        if not config.PINECONE_API_KEY:
            raise ValueError("VECTOR_DB_MODE=cloud 时，必须配置 PINECONE_API_KEY")

    def get_vector_store(self, user_id: int) -> Any:  # 返回类型: PineconeVectorStore
        # Pinecone 是全局单例，user_id 用于过滤，不影响实例获取
        cache_key = "pinecone_global"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # 创建 Pinecone 客户端（新版本 SDK v3+ 不需要 PINECONE_ENVIRONMENT）
        # 确保使用正确的 API key，避免 SSL 证书验证问题
        pc = Pinecone(api_key=config.PINECONE_API_KEY)
        index_name = config.PINECONE_INDEX_NAME
        
        # 检查/创建 Index 逻辑简化，假设已存在或自动创建
        # 实际生产中最好在部署脚本中处理 Index 创建
        
        # 正确初始化 PineconeVectorStore
        # 尝试显式传入 pinecone_client（如果支持），否则使用默认方式
        try:
            vectorstore = PineconeVectorStore(
                index_name=index_name,
                embedding=self.embeddings,
                pinecone_client=pc  # 显式传入客户端实例，避免 SSL 问题
            )
        except TypeError:
            # 如果 pinecone_client 参数不支持，回退到默认方式
            # 但需要确保环境变量 PINECONE_API_KEY 已设置
            logger.warning("[PineconeStrategy] pinecone_client 参数不支持，使用默认初始化方式")
        vectorstore = PineconeVectorStore(
            index_name=index_name,
            embedding=self.embeddings
        )
        
        self._cache[cache_key] = vectorstore
        return vectorstore

    def add_documents(self, user_id: int, documents: List[Document]) -> List[str]:
        # 确保 metadata 包含 user_id
        for doc in documents:
            if "user_id" not in doc.metadata:
                doc.metadata["user_id"] = user_id
        
        vectorstore = self.get_vector_store(user_id)
        return vectorstore.add_documents(documents)

    def delete_documents(self, user_id: int, doc_id: str):
        vectorstore = self.get_vector_store(user_id)
        # 必须同时过滤 user_id 和 doc_id
        vectorstore.delete(filter={"user_id": user_id, "doc_id": doc_id})

    def search(self, user_id: int, query: str, k: int, filter_args: Optional[Dict] = None) -> List[Document]:
        vectorstore = self.get_vector_store(user_id)
        # 强制添加 user_id 过滤
        actual_filter = {"user_id": user_id}
        if filter_args:
            actual_filter.update(filter_args)
        return vectorstore.similarity_search(query, k=k, filter=actual_filter)

    def search_with_score(self, user_id: int, query: str, k: int, filter_args: Optional[Dict] = None) -> List[tuple]:
        vectorstore = self.get_vector_store(user_id)
        actual_filter = {"user_id": user_id}
        if filter_args:
            actual_filter.update(filter_args)
        return vectorstore.similarity_search_with_score(query, k=k, filter=actual_filter)

    def get_document_count(self, user_id: int) -> int:
        # 优化：优先使用数据库统计，因为 Pinecone 统计复杂且昂贵
        try:
            from rag_service.database import DocumentDAO
            doc_dao = DocumentDAO()
            return doc_dao.get_total_chunk_count(user_id, status='active')
        except Exception as e:
            logger.warning(f"[PineconeStrategy] 无法从数据库获取向量数量: {str(e)}")
            return 0

    def clear_cache(self, user_id: Optional[int] = None):
        # Pinecone 是全局的，通常不需要按用户清除，除非清除全局实例
        if not user_id:
            self._cache.clear()
