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
# 本地运行：从 rag_service/.env 或 backend/.env 文件加载
# 云部署：从环境变量加载（.env 不存在时静默失败）
from pathlib import Path
RAG_SERVICE_DIR = Path(__file__).parent.parent
# 优先加载rag_service/.env
if (RAG_SERVICE_DIR / ".env").exists():
    load_dotenv(RAG_SERVICE_DIR / ".env", override=False)

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
    MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 20 * 1024 * 1024))  # 20MB
    
    # RAG 配置（中文书籍优化）
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 1000))  # 从 800 调整为 1000，更适合中文
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 150))  # 从 100 调整为 150，增加上下文重叠
    MIN_CHUNK_SIZE = int(os.getenv("MIN_CHUNK_SIZE", 200))
    MAX_CHUNK_SIZE = int(os.getenv("MAX_CHUNK_SIZE", 1000))
    
    RETRIEVAL_K = int(os.getenv("RETRIEVAL_K", 3))
    RETRIEVAL_SEARCH_TYPE = os.getenv("RETRIEVAL_SEARCH_TYPE", "similarity")
    
    # RAG 降级配置
    RAG_FALLBACK_ENABLED = os.getenv("RAG_FALLBACK_ENABLED", "true").lower() == "true"  # 是否启用降级到直接回答
    RAG_SIMILARITY_THRESHOLD = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.3"))  # 相似度阈值（0-1之间）
    
    # ==================== LangGraph RAG（可选）====================
    USE_LANGGRAPH_RAG = os.getenv("USE_LANGGRAPH_RAG", "false").lower() == "true"
    USE_HYBRID_RETRIEVER = os.getenv("USE_HYBRID_RETRIEVER", "false").lower() == "true"
    HYBRID_RETRIEVER_TOP_K = int(os.getenv("HYBRID_RETRIEVER_TOP_K", 20))

    USE_PARENT_CHILD_STRATEGY = os.getenv("USE_PARENT_CHILD_STRATEGY", "false").lower() == "true"
    # 中文书籍优化：中文单字信息密度更高，适当增大分块大小
    PARENT_CHUNK_SIZE = int(os.getenv("PARENT_CHUNK_SIZE", 1800))  # 从 1200 调整为 1800
    CHILD_CHUNK_SIZE = int(os.getenv("CHILD_CHUNK_SIZE", 450))  # 从 300 调整为 450

    USE_RERANKER = os.getenv("USE_RERANKER", "false").lower() == "true"
    RERANKER_MODEL = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-base")  # 支持中英文的 reranker 模型
    RERANK_SCORE_THRESHOLD = os.getenv("RERANK_SCORE_THRESHOLD", "")
    RERANK_SCORE_THRESHOLD = float(RERANK_SCORE_THRESHOLD) if RERANK_SCORE_THRESHOLD else None
    RERANK_TOP_K = int(os.getenv("RERANK_TOP_K", 20))
    RERANK_TOP_N = int(os.getenv("RERANK_TOP_N", 3))

    MAX_RETRY_COUNT = int(os.getenv("MAX_RETRY_COUNT", 3))
    
    # ==================== LangGraph Checkpoint 配置 ===================
    USE_CHECKPOINT = os.getenv("USE_CHECKPOINT", "true").lower() == "true"  # 是否启用 checkpoint
    CHECKPOINT_TYPE = os.getenv("CHECKPOINT_TYPE", "sqlite").lower()  # memory/sqlite/postgres
    CHECKPOINT_DB_PATH = os.getenv("CHECKPOINT_DB_PATH", "data/checkpoints/checkpoints.db")  # SQLite 数据库路径
    
    # ==================== 消息总结配置 ===================
    USE_MESSAGE_SUMMARIZATION = os.getenv("USE_MESSAGE_SUMMARIZATION", "true").lower() == "true"  # 是否启用消息总结
    MESSAGE_SUMMARIZATION_THRESHOLD = int(os.getenv("MESSAGE_SUMMARIZATION_THRESHOLD", "8000"))  # 触发总结的 token 阈值
    MESSAGE_SUMMARIZATION_KEEP_MESSAGES = int(os.getenv("MESSAGE_SUMMARIZATION_KEEP_MESSAGES", "20"))  # 总结后保留的消息数量
    MESSAGE_SUMMARIZATION_MODEL = os.getenv("MESSAGE_SUMMARIZATION_MODEL", "")  # 可选：专门的总结模型（如果为空，则使用主模型）
    MESSAGE_SUMMARIZATION_MAX_TOKENS = int(os.getenv("MESSAGE_SUMMARIZATION_MAX_TOKENS", "500"))  # 总结的最大 token 数
    
    # LLM 配置
    LLM_MODEL = os.getenv("LLM_MODEL", "MiniMax-M2")
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", 0))
    LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", 2000))
    
    # Embedding 配置
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5")
    EMBEDDING_DEVICE = os.getenv("EMBEDDING_DEVICE", "cpu")
    NORMALIZE_EMBEDDINGS = os.getenv("NORMALIZE_EMBEDDINGS", "true").lower() == "true"
    # 模型下载源：huggingface 或 modelscope
    MODEL_DOWNLOAD_SOURCE = os.getenv("MODEL_DOWNLOAD_SOURCE", "modelscope").lower()

    # 推理服务（ngrok）配置
    INFERENCE_API_BASE_URL = os.getenv(
        "INFERENCE_API_BASE_URL", ""
    )
    INFERENCE_API_KEY = os.getenv("INFERENCE_API_KEY", "")
    USE_REMOTE_EMBEDDINGS = os.getenv("USE_REMOTE_EMBEDDINGS", "false").lower() == "true"
    USE_REMOTE_RERANKER = os.getenv("USE_REMOTE_RERANKER", "false").lower() == "true"
    INFERENCE_API_TIMEOUT = float(os.getenv("INFERENCE_API_TIMEOUT", "15"))
    INFERENCE_API_MAX_RETRY = int(os.getenv("INFERENCE_API_MAX_RETRY", "2"))
    
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

