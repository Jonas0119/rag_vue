"""
配置管理
"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


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


# 全局配置实例
config = Config()

