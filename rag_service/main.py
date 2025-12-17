"""
RAG Service FastAPI 应用主入口
启动时预加载 Embedding、Rerank 模型以及向量库 / 存储等依赖
"""
import logging
import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from rag_service.utils.config import config

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
    """
    应用生命周期管理 - 启动时预加载核心依赖
    
    - Embedding 模型
    - Rerank 模型（可选）
    - 向量库客户端
    - Supabase Storage（云存储模式）
    - 文本分块 / 清洗工具（轻量预热）
    """
    logger.info("🚀 RAG Service 启动中...")

    warmup_status = {
        "embedding": False,
        "reranker": False,
        "vector_store": False,
        "supabase_storage": False,
        "text_splitter": False,
    }

    # 预加载 Embedding 模型（从 ModelScope / HuggingFace 下载）
    try:
        logger.info(
            f"📥 开始预加载 Embedding 模型: {config.EMBEDDING_MODEL} "
            f"(source={config.MODEL_DOWNLOAD_SOURCE})"
        )
        from rag_service.services.vector_store_service import get_vector_store_service

        vector_service = get_vector_store_service()
        # 等待模型加载完成（最多等待 5 分钟）
        if vector_service._ensure_embeddings_loaded(timeout=300.0):
            warmup_status["embedding"] = True
            warmup_status["vector_store"] = True
            logger.info("✅ Embedding 模型加载完成，向量库客户端可用")
        else:
            logger.warning("⚠️ Embedding 模型加载超时，将在首次请求时懒加载")
    except Exception as e:
        logger.error(f"❌ Embedding / 向量库预热失败: {str(e)}", exc_info=True)
        logger.warning("⚠️ 将在首次使用时尝试加载")

    # 预加载 Rerank 模型（如果启用）
    if config.USE_RERANKER:
        try:
            logger.info(
                f"📥 开始预加载 Rerank 模型: {config.RERANKER_MODEL} "
                f"(source={config.MODEL_DOWNLOAD_SOURCE})"
            )
            from rag_service.services.reranker import CrossEncoderReranker

            _ = CrossEncoderReranker()
            warmup_status["reranker"] = True
            logger.info("✅ Rerank 模型加载完成")
        except Exception as e:
            logger.error(f"❌ Rerank 模型加载失败: {str(e)}", exc_info=True)
            logger.warning("⚠️ 将在首次使用时尝试加载")
    else:
        logger.info("ℹ️ Reranker 未启用，跳过模型加载")

    # 预热 Supabase Storage（云存储模式）
    if config.STORAGE_MODE == "cloud":
        try:
            from rag_service.utils.supabase_storage import get_supabase_storage

            storage = get_supabase_storage()
            if storage is not None:
                warmup_status["supabase_storage"] = True
                logger.info("✅ SupabaseStorage 初始化完成")
            else:
                logger.warning("⚠️ SupabaseStorage 未启用或配置不完整，跳过预热")
        except Exception as e:
            logger.error(f"❌ SupabaseStorage 预热失败: {str(e)}", exc_info=True)
    else:
        logger.info("ℹ️ STORAGE_MODE!=cloud，跳过 SupabaseStorage 预热")

    # 预热文本分块 / 父子分块等工具（主要是导入模块，避免首次请求才导入）
    try:
        # 仅导入模块即可触发内部正则 / 类的加载，避免首次使用时的 import 开销
        import rag_service.utils.text_splitter  # noqa: F401
        import rag_service.utils.parent_child_splitter  # noqa: F401

        warmup_status["text_splitter"] = True
        logger.info("✅ 文本分块 / 父子分块工具模块导入完成")
    except Exception as e:
        logger.warning(f"⚠️ 文本分块工具预热失败（不影响服务启动）: {e}", exc_info=True)

    logger.info("✅ RAG Service 启动完成")

    # 将预热状态挂到 app.state 便于健康检查使用
    app.state.warmup_status = warmup_status

    yield

    # 关闭时执行
    logger.info("🛑 RAG Service 关闭中...")


# 创建 FastAPI 应用
app = FastAPI(
    title="RAG Service API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# 配置 CORS（允许所有来源，因为通过ngrok暴露）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
            "message": str(exc)
        }
    )


# 健康检查端点
@app.get("/")
async def root():
    """根路径"""
    from rag_service.services.vector_store_service import get_vector_store_service
    vector_service = get_vector_store_service()
    
    return {
        "message": "RAG Service API",
        "version": "1.0.0",
        "status": "running",
        "embedding_ready": vector_service.is_embeddings_ready(),
        "embedding_model": config.EMBEDDING_MODEL,
        "reranker_enabled": config.USE_RERANKER,
        "reranker_model": config.RERANKER_MODEL if config.USE_RERANKER else None,
    }


@app.get("/health")
async def health_check():
    """
    健康检查
    
    返回 RAG Service 自身状态、模型 / 向量库 / 存储等依赖的健康信息。
    """
    from rag_service.services.vector_store_service import get_vector_store_service

    vector_service = get_vector_store_service()

    # 读取启动阶段的预热结果（如果存在）
    warmup_status = getattr(app.state, "warmup_status", {})

    return {
        "status": "healthy",
        "embedding_loaded": vector_service.is_embeddings_ready(),
        "embedding_model": config.EMBEDDING_MODEL,
        "reranker_enabled": config.USE_RERANKER,
        "storage_mode": config.STORAGE_MODE,
        "warmup": warmup_status,
    }


# 导入并注册路由
from rag_service.api import chat, documents

app.include_router(chat.router, tags=["对话"])
app.include_router(documents.router, tags=["文档"])


if __name__ == "__main__":
    import uvicorn
    
    # 从环境变量获取端口，默认8001
    port = int(os.getenv("RAG_SERVICE_PORT", "8001"))
    host = os.getenv("RAG_SERVICE_HOST", "0.0.0.0")
    
    logger.info(f"🌐 启动 RAG Service，监听 {host}:{port}")
    logger.info(f"📝 通过 ngrok 暴露后，设置 backend 的 RAG_SERVICE_URL 环境变量")
    
    uvicorn.run(
        "rag_service.main:app",
        host=host,
        port=port,
        reload=False,  # 生产环境不启用reload
        log_level="info",
    )


