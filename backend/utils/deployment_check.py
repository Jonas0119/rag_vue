"""
部署配置检查工具
用于验证 Streamlit Cloud 部署所需的配置是否完整
"""
import os
import logging
from typing import List, Tuple

from backend.utils.config import config

logger = logging.getLogger(__name__)


def check_cloud_deployment_config() -> Tuple[bool, List[str]]:
    """
    检查云部署配置是否完整
    
    Returns:
        (是否通过, 错误信息列表)
    """
    errors = []
    warnings = []
    
    # 检查模式配置
    if config.STORAGE_MODE != "cloud":
        warnings.append(f"STORAGE_MODE={config.STORAGE_MODE}，建议在 Streamlit Cloud 上使用 'cloud'")
    
    if config.VECTOR_DB_MODE != "cloud":
        warnings.append(f"VECTOR_DB_MODE={config.VECTOR_DB_MODE}，建议在 Streamlit Cloud 上使用 'cloud'")
    
    if config.DATABASE_MODE != "cloud":
        warnings.append(f"DATABASE_MODE={config.DATABASE_MODE}，建议在 Streamlit Cloud 上使用 'cloud'")
    
    # 检查必需的基础配置
    if not config.ANTHROPIC_API_KEY or config.ANTHROPIC_API_KEY == "":
        errors.append("ANTHROPIC_API_KEY 未配置")
    
    if not config.AUTH_COOKIE_KEY or config.AUTH_COOKIE_KEY == "default_secret_key":
        errors.append("AUTH_COOKIE_KEY 未配置或使用默认值（不安全）")
    
    # 检查云服务配置（根据模式）
    if config.STORAGE_MODE == "cloud":
        if not config.SUPABASE_URL or "your-project" in config.SUPABASE_URL:
            errors.append("STORAGE_MODE=cloud 但 SUPABASE_URL 未配置或使用占位符")
        
        if not config.SUPABASE_SERVICE_KEY or "your_service_key" in config.SUPABASE_SERVICE_KEY:
            errors.append("STORAGE_MODE=cloud 但 SUPABASE_SERVICE_KEY 未配置或使用占位符")
        
        if not config.SUPABASE_STORAGE_BUCKET:
            errors.append("STORAGE_MODE=cloud 但 SUPABASE_STORAGE_BUCKET 未配置")
    
    if config.DATABASE_MODE == "cloud":
        if not config.DATABASE_URL or "your_password" in config.DATABASE_URL:
            errors.append("DATABASE_MODE=cloud 但 DATABASE_URL 未配置或使用占位符")
    
    if config.VECTOR_DB_MODE == "cloud":
        if not config.PINECONE_API_KEY or "your_pinecone" in config.PINECONE_API_KEY:
            errors.append("VECTOR_DB_MODE=cloud 但 PINECONE_API_KEY 未配置或使用占位符")
        
        # 注意：Pinecone v6.0.0+ 不再需要 PINECONE_ENVIRONMENT
        # 新版本使用不同的 API 架构，环境信息包含在 API Key 中
        # 保留此检查仅作为警告，不阻止部署
        if not config.PINECONE_ENVIRONMENT:
            warnings.append("PINECONE_ENVIRONMENT 未配置（Pinecone v6.0.0+ 不再需要，但保留配置也无妨）")
        
        if not config.PINECONE_INDEX_NAME:
            errors.append("VECTOR_DB_MODE=cloud 但 PINECONE_INDEX_NAME 未配置")
    
    # 检查是否在 Streamlit Cloud 环境
    is_streamlit_cloud = os.getenv("STREAMLIT_CLOUD", "").lower() == "true"
    
    if is_streamlit_cloud and config.STORAGE_MODE != "cloud":
        errors.append("在 Streamlit Cloud 上必须使用 STORAGE_MODE=cloud")
    
    if is_streamlit_cloud and config.DATABASE_MODE != "cloud":
        errors.append("在 Streamlit Cloud 上必须使用 DATABASE_MODE=cloud")
    
    if is_streamlit_cloud and config.VECTOR_DB_MODE != "cloud":
        errors.append("在 Streamlit Cloud 上必须使用 VECTOR_DB_MODE=cloud")
    
    return len(errors) == 0, errors + warnings


def show_deployment_status():
    """在 Streamlit 中显示部署状态"""
    import streamlit as st
    
    is_ok, messages = check_cloud_deployment_config()
    
    if is_ok and not messages:
        st.success("✅ 部署配置检查通过")
        return True
    
    if messages:
        # 分离错误和警告
        errors = [m for m in messages if not m.startswith("STORAGE_MODE") and not m.startswith("VECTOR_DB_MODE") and not m.startswith("DATABASE_MODE")]
        warnings = [m for m in messages if m not in errors]
        
        if errors:
            st.error("❌ 配置错误：")
            for error in errors:
                st.error(f"  • {error}")
        
        if warnings:
            st.warning("⚠️ 配置警告：")
            for warning in warnings:
                st.warning(f"  • {warning}")
    
    return is_ok

