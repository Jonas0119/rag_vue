"""
FastAPI 核心配置
"""
import os
import sys
from pathlib import Path

# 获取 backend 目录
# 在 Vercel 环境中，__file__ 可能未定义，使用备用方法
try:
    BACKEND_DIR = Path(__file__).parent.parent
except NameError:
    # 如果 __file__ 未定义（动态导入），尝试从 sys.path 推断
    # 在 Vercel 上，backend 目录的内容在 /var/task/
    if '/var/task' in str(sys.path[0]) if sys.path else '':
        BACKEND_DIR = Path('/var/task')
    else:
        # 回退到当前工作目录
        BACKEND_DIR = Path.cwd()

# 获取项目根目录（用于其他路径引用）
BASE_DIR = BACKEND_DIR.parent

# 加载环境变量（从 backend/.env 加载）
from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env", override=False)

class Settings:
    """FastAPI 应用配置"""
    
    # API 配置
    API_V1_PREFIX: str = "/api"
    PROJECT_NAME: str = "RAG 智能问答系统 API"
    VERSION: str = "1.0.0"
    
    # CORS 配置
    CORS_ORIGINS: list = [
        "http://localhost:5173",  # Vite 开发服务器
        "http://localhost:3000",   # 备用端口
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]
    
    # 开发模式：允许所有源（用于局域网访问）
    CORS_ALLOW_ALL: bool = os.getenv("CORS_ALLOW_ALL", "true").lower() == "true"
    
    # 认证配置
    AUTH_COOKIE_NAME: str = os.getenv("AUTH_COOKIE_NAME", "rag_auth_token")
    AUTH_COOKIE_KEY: str = os.getenv("AUTH_COOKIE_KEY", "default_secret_key")
    AUTH_COOKIE_EXPIRY_DAYS: int = int(os.getenv("AUTH_COOKIE_EXPIRY_DAYS", 30))
    
    # JWT 配置
    JWT_SECRET_KEY: str = AUTH_COOKIE_KEY
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_DAYS: int = AUTH_COOKIE_EXPIRY_DAYS
    
    # 文件上传配置（与 utils.config.MAX_FILE_SIZE 一致，默认 30MB）
    MAX_UPLOAD_SIZE: int = int(os.getenv("MAX_FILE_SIZE", 30 * 1024 * 1024))  # 30MB
    UPLOAD_DIR: Path = BASE_DIR / "data" / "uploads"
    
    # 调试模式
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    @classmethod
    def get_cors_origins(cls) -> list:
        """获取 CORS 允许的源"""
        # 开发模式：允许所有源（用于局域网访问）
        if cls.CORS_ALLOW_ALL:
            return ["*"]
        
        # 从环境变量读取额外的 CORS 源
        extra_origins = os.getenv("CORS_ORIGINS", "")
        if extra_origins:
            cls.CORS_ORIGINS.extend([origin.strip() for origin in extra_origins.split(",")])
        return cls.CORS_ORIGINS


settings = Settings()
