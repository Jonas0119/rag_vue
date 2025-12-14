# services/cache_service.py
"""统一缓存层，用于系统设置页面的查询缓存。
使用 Streamlit 的 @st.cache_data，TTL 设为 120 秒（可根据需求调整）。
所有缓存函数均返回普通数据结构（dict、list），便于在 UI 中直接使用。
"""

import streamlit as st
from .user_service import get_user_service
from .session_service import get_session_service
from .document_service import get_document_service

# ---------- 用户信息缓存 ----------
@st.cache_data(ttl=120)
def get_cached_user(user_id: int):
    """缓存单个用户的基本信息（不包括敏感字段）。
    返回值为 dict，来源于 UserDAO.get_user_by_id 转换后的模型。
    """
    user_service = get_user_service()
    user = user_service.get_user_by_id(user_id)
    if not user:
        return {}
    # 只返回前端需要的字段，避免泄露密码哈希等敏感信息
    return {
        "user_id": user.user_id,
        "username": user.username,
        "email": user.email,
        "display_name": user.display_name,
        "avatar_url": getattr(user, "avatar_url", None),
        "created_at": user.created_at,
        "last_login": user.last_login,
    }

# ---------- 会话列表缓存 ----------
@st.cache_data(ttl=120)
def get_cached_sessions(user_id: int):
    """缓存用户的会话列表（按时间分组）。
    返回 Dict[str, List[Dict]]，例如 {'今天': [...], '昨天': [...]}
    """
    session_service = get_session_service()
    return session_service.get_user_sessions(user_id=user_id)

# ---------- 文档统计缓存 ----------
@st.cache_data(ttl=120)
def get_cached_user_stats(user_id: int):
    """缓存文档统计信息（文档数、存储大小、向量数）。"""
    doc_service = get_document_service()
    return doc_service.get_user_stats(user_id)
