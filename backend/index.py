"""
Vercel 入口文件 - 最小化导出，避免误检测
直接导入 app，Vercel 会自动处理 FastAPI 应用
"""
# 直接导入 app
from main import app

# 只导出 app
__all__ = ['app']
