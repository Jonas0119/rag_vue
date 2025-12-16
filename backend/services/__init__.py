"""
服务层模块（Vercel 轻量网关）

仅保留与用户、会话、文档元数据相关的服务。
所有 RAG / 向量库逻辑已经迁移到 rag_service 中。
"""
from .document_service import DocumentService, get_document_service
from .session_service import SessionService, get_session_service
from .user_service import UserService, get_user_service
# cache_service 仅用于 Streamlit，FastAPI 后端不需要
# from .cache_service import get_cached_user, get_cached_sessions, get_cached_user_stats

__all__ = [
    'DocumentService',
    'get_document_service',
    'SessionService',
    'get_session_service',
    'UserService',
    'get_user_service',
]
