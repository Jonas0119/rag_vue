"""
FastAPI 应用主入口
"""
import logging
import sys
from pathlib import Path
from contextlib import asynccontextmanager

# 添加项目根目录到 Python 路径（支持从项目根目录或 backend 目录运行）
# 在 Vercel 上，Root Directory 是 backend/，所以 backend/ 的内容被复制到 /var/task/
# 这意味着 main.py 在 /var/task/，core/, api/ 等目录也在 /var/task/ 下
# 但代码使用 from backend.xxx 导入，所以需要创建 backend 模块映射
current_file = Path(__file__).resolve()
current_dir = current_file.parent

# 检查是否在 Vercel 环境（/var/task/）
if str(current_dir) == "/var/task":
    # Vercel 环境：backend/ 目录的内容被直接复制到 /var/task/
    # 创建一个导入钩子，将 backend.xxx 重定向到当前目录的 xxx
    import importlib
    import importlib.abc
    import importlib.machinery
    import types
    
    class BackendImportFinder(importlib.abc.MetaPathFinder):
        """将 backend.xxx 导入重定向到当前目录的 xxx"""
        def find_spec(self, name, path, target=None):
            if name.startswith('backend.'):
                # 将 backend.xxx 转换为当前目录下的 xxx
                submodule_name = name[8:]  # 去掉 'backend.' 前缀
                parts = submodule_name.split('.')
                module_path = current_dir
                
                # 构建模块路径
                for part in parts:
                    module_path = module_path / part
                
                # 检查是否是文件或目录
                if module_path.is_file() and module_path.suffix == '.py':
                    # Python 文件
                    loader = importlib.machinery.SourceFileLoader(name, str(module_path))
                    return importlib.machinery.ModuleSpec(name, loader)
                elif module_path.is_dir():
                    # 目录（包）
                    init_file = module_path / '__init__.py'
                    loader = importlib.machinery.SourceFileLoader(name, str(init_file)) if init_file.exists() else None
                    spec = importlib.machinery.ModuleSpec(name, loader)
                    spec.submodule_search_locations = [str(module_path)]
                    return spec
                elif (module_path.parent.is_dir() and 
                      (module_path.parent / '__init__.py').exists()):
                    # 可能是包内的模块文件
                    py_file = module_path.with_suffix('.py')
                    if py_file.exists():
                        loader = importlib.machinery.SourceFileLoader(name, str(py_file))
                        return importlib.machinery.ModuleSpec(name, loader)
            return None
    
    # 注册导入钩子
    sys.meta_path.insert(0, BackendImportFinder())
    
    # 将当前目录添加到路径
    if str(current_dir) not in sys.path:
        sys.path.insert(0, str(current_dir))
    
    project_root = current_dir
else:
    # 本地环境：main.py 在 backend/，项目根目录在 backend/../
    project_root = current_dir.parent
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
    """应用生命周期管理（Backend 仅作为轻量网关，不加载任何模型）"""
    logger.info("🚀 FastAPI 网关启动中...")
    yield
    logger.info("🛑 FastAPI 网关关闭中...")


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
