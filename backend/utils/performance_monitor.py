"""
性能监控工具
记录远程云服务的调用时间
"""
import time
import logging
from functools import wraps
from contextlib import contextmanager
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """性能监控器"""
    
    @staticmethod
    def log_operation(service_name: str, operation: str, duration: float, 
                     success: bool = True, details: Optional[str] = None):
        """
        记录操作性能
        
        Args:
            service_name: 服务名称（如 "Supabase Storage", "Pinecone", "PostgreSQL"）
            operation: 操作名称（如 "upload_file", "query", "execute_query"）
            duration: 耗时（秒）
            success: 是否成功
            details: 额外详情
        """
        # 性能监控日志已注释
        # status = "✅" if success else "❌"
        # duration_ms = duration * 1000
        # 
        # log_msg = f"[性能监控] {status} {service_name} | {operation} | {duration_ms:.2f}ms"
        # if details:
        #     log_msg += f" | {details}"
        # 
        # # 根据耗时选择日志级别
        # if duration > 5.0:
        #     logger.warning(log_msg)
        # elif duration > 2.0:
        #     logger.info(log_msg)
        # else:
        #     logger.debug(log_msg)
        pass
    
    @staticmethod
    def monitor_function(service_name: str, operation_name: Optional[str] = None):
        """
        函数性能监控装饰器
        
        用法:
            @PerformanceMonitor.monitor_function("Supabase Storage", "upload_file")
            def upload_file(...):
                ...
        """
        def decorator(func: Callable):
            op_name = operation_name or func.__name__
            
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                success = True
                error_msg = None
                
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    success = False
                    error_msg = str(e)
                    raise
                finally:
                    duration = time.time() - start_time
                    details = f"error: {error_msg}" if error_msg else None
                    PerformanceMonitor.log_operation(
                        service_name, op_name, duration, success, details
                    )
            
            return wrapper
        return decorator
    
    @staticmethod
    @contextmanager
    def monitor_operation(service_name: str, operation: str, details: Optional[str] = None):
        """
        操作性能监控上下文管理器
        
        用法:
            with PerformanceMonitor.monitor_operation("Pinecone", "query", "top_k=5"):
                # 执行操作
                ...
        """
        start_time = time.time()
        success = True
        error_msg = None
        
        try:
            yield
        except Exception as e:
            success = False
            error_msg = str(e)
            raise
        finally:
            duration = time.time() - start_time
            full_details = details
            if error_msg:
                full_details = f"{details} | error: {error_msg}" if details else f"error: {error_msg}"
            PerformanceMonitor.log_operation(
                service_name, operation, duration, success, full_details
            )


# 便捷函数
def monitor_storage(operation: str, details: Optional[str] = None):
    """监控存储服务操作"""
    return PerformanceMonitor.monitor_operation("Supabase Storage", operation, details)


def monitor_vector_db(operation: str, details: Optional[str] = None):
    """监控向量数据库操作"""
    return PerformanceMonitor.monitor_operation("Pinecone", operation, details)


def monitor_database(operation: str, details: Optional[str] = None):
    """监控数据库操作"""
    return PerformanceMonitor.monitor_operation("PostgreSQL", operation, details)

