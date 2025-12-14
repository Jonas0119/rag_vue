"""
FastAPI 应用主入口
"""
import logging
import sys
from pathlib import Path
from contextlib import asynccontextmanager

# 添加项目根目录到 Python 路径（支持从项目根目录或 backend 目录运行）
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.core.config import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)d | %(funcName)s() | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout,
    force=True
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("🚀 FastAPI 应用启动中...")
    
    # 预加载 Embedding 模型（后台加载，不阻塞启动）
    try:
        from backend.services import get_vector_store_service
        _ = get_vector_store_service()
        logger.info("✅ Embedding 模型后台加载已触发")
    except Exception as e:
        logger.warning(f"⚠️ Embedding 模型加载失败: {str(e)}")
    
    yield
    
    # 关闭时执行
    logger.info("🛑 FastAPI 应用关闭中...")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理器"""
    logger.error(f"未处理的异常: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "服务器内部错误",
            "message": str(exc) if settings.DEBUG else "服务器内部错误，请稍后重试"
        }
    )


# 健康检查端点
@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "RAG 智能问答系统 API",
        "version": settings.VERSION,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


# 导入并注册路由
from backend.api import auth, chat, documents, sessions

app.include_router(auth.router, prefix=settings.API_V1_PREFIX, tags=["认证"])
app.include_router(chat.router, prefix=settings.API_V1_PREFIX, tags=["对话"])
app.include_router(documents.router, prefix=settings.API_V1_PREFIX, tags=["文档"])
app.include_router(sessions.router, prefix=settings.API_V1_PREFIX, tags=["会话"])


# Vercel Serverless Functions 适配
try:
    from mangum import Mangum
    handler = Mangum(app)
except ImportError:
    # 本地开发时不需要 mangum
    handler = None


if __name__ == "__main__":
    import uvicorn
    # 从项目根目录运行
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        reload_dirs=[str(project_root)]
    )
