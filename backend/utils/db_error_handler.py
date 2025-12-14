"""
数据库错误处理工具
提供统一的数据库连接错误处理机制
"""
from typing import Callable, Any, Optional
import logging

logger = logging.getLogger(__name__)

# 尝试导入 streamlit（可选，仅用于 UI 显示）
try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False
    st = None


class DatabaseConnectionError(Exception):
    """数据库连接错误（自定义异常类）"""
    pass


def handle_db_error(func: Callable) -> Callable:
    """
    数据库操作错误处理装饰器
    
    用法:
        @handle_db_error
        def my_db_operation():
            # 数据库操作
            pass
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ConnectionError as e:
            error_msg = str(e)
            # 检查是否是数据库连接错误
            if "无法连接到" in error_msg or "数据库连接失败" in error_msg:
                raise DatabaseConnectionError(error_msg) from e
            else:
                raise
        except Exception as e:
            logger.error(f"[数据库操作] {func.__name__} 失败: {str(e)}")
            raise
    
    return wrapper


def show_db_error_ui(error: Exception, context: str = "操作"):
    """
    在 UI 中显示数据库错误提示（仅当 Streamlit 可用时）
    
    Args:
        error: 异常对象
        context: 操作上下文（如 "获取文档列表"、"保存会话" 等）
    """
    error_msg = str(error)
    
    if not HAS_STREAMLIT:
        # 非 Streamlit 环境，仅记录日志
        logger.error(f"⚠️ 无法连接到数据库，{context}失败: {error_msg}")
        return
    
    # 检查是否是数据库连接错误
    if "无法连接到" in error_msg or "数据库连接失败" in error_msg or "DNS 解析失败" in error_msg:
        st.error(f"⚠️ 无法连接到数据库，{context}失败")
        
        # 检查是否是 DNS 解析失败
        if "DNS 解析失败" in error_msg or "nodename nor servname" in error_msg:
            with st.expander("🔍 查看详细错误信息和解决方案", expanded=True):
                st.warning("""
                **网络连接问题**
                
                无法连接到 Supabase PostgreSQL 数据库。这可能是由于：
                - 网络连接不稳定
                - DNS 解析失败
                - 防火墙阻止了连接
                
                **解决方案：**
                1. 检查网络连接
                2. 确认 `backend/.env` 文件中的 `DATABASE_URL` 配置正确
                3. 如果问题持续，可以暂时切换到本地模式：
                   - 在 `backend/.env` 文件中设置 `DATABASE_MODE=local`
                   - 重启应用
                """)
                st.code(error_msg, language=None)
        else:
            with st.expander("🔍 查看详细错误信息", expanded=False):
                st.warning(error_msg)
    else:
        st.error(f"❌ {context}失败: {error_msg}")


def safe_db_operation(operation: Callable, default_value: Any = None, 
                      error_context: str = "数据库操作") -> Any:
    """
    安全执行数据库操作，捕获错误并返回默认值
    
    Args:
        operation: 要执行的数据库操作（函数）
        default_value: 出错时返回的默认值
        error_context: 错误上下文描述
    
    Returns:
        操作结果或默认值
    """
    try:
        return operation()
    except DatabaseConnectionError as e:
        logger.error(f"[数据库操作] {error_context} 失败: {str(e)}")
        show_db_error_ui(e, error_context)
        return default_value
    except ConnectionError as e:
        logger.error(f"[数据库操作] {error_context} 连接失败: {str(e)}")
        show_db_error_ui(e, error_context)
        return default_value
    except Exception as e:
        logger.error(f"[数据库操作] {error_context} 失败: {str(e)}")
        if HAS_STREAMLIT:
            st.error(f"❌ {error_context}失败: {str(e)}")
        return default_value

