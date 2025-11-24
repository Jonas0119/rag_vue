"""
配置管理
兼容本地运行和 Streamlit Cloud 部署

环境变量加载优先级：
1. 系统环境变量（Streamlit Cloud Secrets）
2. .env 文件（本地开发）
3. 默认值
"""
import os
from dotenv import load_dotenv

# 加载环境变量
# 本地运行：从 .env 文件加载
# Streamlit Cloud：从 Secrets 加载（.env 不存在时静默失败）
load_dotenv(override=False)  # override=False 确保环境变量优先级：系统环境变量 > .env 文件

# 在 Streamlit Cloud 中，Secrets 会自动加载到 st.secrets
# 这里将 st.secrets 中的值合并到环境变量（如果存在）
# 注意：此代码在模块导入时执行，此时 Streamlit 可能还未初始化
# 因此使用延迟加载，在首次访问时再尝试加载 Secrets
def _load_streamlit_secrets():
    """
    延迟加载 Streamlit Secrets
    
    在 Streamlit Cloud 中，Secrets 会自动加载到 st.secrets
    本地开发时，如果 .streamlit/secrets.toml 不存在，会抛出 StreamlitSecretNotFoundError
    这里捕获该异常，确保本地开发时不会因为缺少 secrets 文件而失败
    """
    try:
        import streamlit as st
        from streamlit.errors import StreamlitSecretNotFoundError
        
        # 检查 secrets 是否存在且可用
        if hasattr(st, 'secrets'):
            try:
                # 尝试访问 secrets，如果文件不存在会抛出 StreamlitSecretNotFoundError
                # 使用 len() 来触发 secrets 的解析，如果文件不存在会立即抛出异常
                _ = len(st.secrets)
                # 如果成功，说明 secrets 存在，可以安全地遍历
                for key, value in st.secrets.items():
                    if key not in os.environ:  # 不覆盖已存在的环境变量
                        os.environ[key] = str(value)
            except StreamlitSecretNotFoundError:
                # secrets 文件不存在，这是正常的（本地开发时使用 .env 文件）
                # 静默忽略，不影响应用启动
                pass
            except Exception:
                # 其他可能的异常（如 RuntimeError），忽略
                pass
    except (ImportError, RuntimeError, AttributeError):
        # 如果不在 Streamlit 环境中或 streamlit 模块不可用，忽略错误
        pass

# 尝试加载 Streamlit Secrets（如果可用）
_load_streamlit_secrets()


class Config:
    """系统配置"""
    
    # API 配置
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")
    
    # 数据库配置
    DATABASE_PATH = os.getenv("DATABASE_PATH", "data/database/rag_system.db")
    
    # 存储配置
    DATA_ROOT_DIR = os.getenv("DATA_ROOT_DIR", "data")
    USER_DATA_DIR = os.getenv("USER_DATA_DIR", "data/users")
    CHROMA_DB_DIR = os.getenv("CHROMA_DB_DIR", "data/chroma")
    MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 10 * 1024 * 1024))  # 10MB
    
    # RAG 配置
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 800))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 100))
    MIN_CHUNK_SIZE = int(os.getenv("MIN_CHUNK_SIZE", 200))
    MAX_CHUNK_SIZE = int(os.getenv("MAX_CHUNK_SIZE", 1000))
    
    RETRIEVAL_K = int(os.getenv("RETRIEVAL_K", 3))
    RETRIEVAL_SEARCH_TYPE = os.getenv("RETRIEVAL_SEARCH_TYPE", "similarity")
    
    # LLM 配置
    LLM_MODEL = os.getenv("LLM_MODEL", "MiniMax-M2")
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", 0))
    LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", 2000))
    
    # Embedding 配置
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5")
    EMBEDDING_DEVICE = os.getenv("EMBEDDING_DEVICE", "cpu")
    NORMALIZE_EMBEDDINGS = os.getenv("NORMALIZE_EMBEDDINGS", "true").lower() == "true"
    
    # 认证配置
    AUTH_COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "rag_auth_token")
    AUTH_COOKIE_KEY = os.getenv("AUTH_COOKIE_KEY", "default_secret_key")
    AUTH_COOKIE_EXPIRY_DAYS = int(os.getenv("AUTH_COOKIE_EXPIRY_DAYS", 30))
    MIN_PASSWORD_LENGTH = int(os.getenv("MIN_PASSWORD_LENGTH", 6))
    
    # ==================== 存储模式切换 ====================
    # local: 使用本地文件系统/SQLite/Chroma
    # cloud: 使用云服务（Supabase/Pinecone）
    STORAGE_MODE = os.getenv("STORAGE_MODE", "local")
    VECTOR_DB_MODE = os.getenv("VECTOR_DB_MODE", "local")
    DATABASE_MODE = os.getenv("DATABASE_MODE", "local")
    
    # ==================== Supabase 配置 ====================
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
    SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
    SUPABASE_STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "rag")
    
    # ==================== Supabase PostgreSQL 配置 ====================
    DATABASE_URL = os.getenv("DATABASE_URL", "")
    
    # ==================== Pinecone 配置 ====================
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
    PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT", "")
    PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "rag-system")


# 全局配置实例
config = Config()

