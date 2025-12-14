"""
Supabase Storage 封装
"""
from typing import Optional, Tuple
import logging
from supabase import create_client, Client

from backend.utils.config import config
from backend.utils.performance_monitor import monitor_storage

logger = logging.getLogger(__name__)


class SupabaseStorage:
    """Supabase Storage 客户端"""
    
    def __init__(self):
        """初始化 Supabase Storage 客户端"""
        if not config.SUPABASE_URL or not config.SUPABASE_SERVICE_KEY:
            raise ValueError("Supabase URL 和 Service Key 必须配置")
        
        self.client: Client = create_client(
            config.SUPABASE_URL,
            config.SUPABASE_SERVICE_KEY  # 使用 Service Key 有完整权限
        )
        self.bucket_name = config.SUPABASE_STORAGE_BUCKET
    
    def upload_file(self, file_data: bytes, file_path: str, content_type: str = "application/octet-stream") -> Tuple[bool, str]:
        """
        上传文件到 Supabase Storage
        
        Args:
            file_data: 文件二进制数据
            file_path: 文件路径（格式：user_{user_id}/{filename}）
            content_type: 文件 MIME 类型
        
        Returns:
            (是否成功, 文件路径或错误信息)
        """
        file_size = len(file_data)
        details = f"size={file_size} bytes, path={file_path}"
        
        with monitor_storage("upload_file", details):
            try:
                response = self.client.storage.from_(self.bucket_name).upload(
                    path=file_path,
                    file=file_data,
                    file_options={
                        "content-type": content_type,
                        "upsert": "false"  # 不覆盖已存在的文件
                    }
                )
                logger.info(f"[Supabase Storage] 文件上传成功: {file_path}")
                return True, file_path
            except Exception as e:
                error_msg = str(e)
                logger.error(f"[Supabase Storage] 文件上传失败: {file_path}, 错误: {error_msg}")
                return False, error_msg
    
    def download_file(self, file_path: str) -> Optional[bytes]:
        """
        从 Supabase Storage 下载文件
        
        Args:
            file_path: 文件路径（格式：user_{user_id}/{filename}）
        
        Returns:
            文件二进制数据，失败返回 None
        """
        with monitor_storage("download_file", f"path={file_path}"):
            try:
                response = self.client.storage.from_(self.bucket_name).download(file_path)
                file_size = len(response) if response else 0
                logger.info(f"[Supabase Storage] 文件下载成功: {file_path}, size={file_size} bytes")
                return response
            except Exception as e:
                logger.error(f"[Supabase Storage] 文件下载失败: {file_path}, 错误: {str(e)}")
                return None
    
    def delete_file(self, file_path: str) -> bool:
        """
        从 Supabase Storage 删除文件
        
        Args:
            file_path: 文件路径
        
        Returns:
            是否成功
        """
        with monitor_storage("delete_file", f"path={file_path}"):
            try:
                self.client.storage.from_(self.bucket_name).remove([file_path])
                logger.info(f"[Supabase Storage] 文件删除成功: {file_path}")
                return True
            except Exception as e:
                logger.error(f"[Supabase Storage] 文件删除失败: {file_path}, 错误: {str(e)}")
                return False
    
    def get_file_url(self, file_path: str, expires_in: int = 3600) -> Optional[str]:
        """
        获取文件的签名 URL（用于私有 Bucket）
        
        Args:
            file_path: 文件路径
            expires_in: URL 有效期（秒），默认 1 小时
        
        Returns:
            文件 URL，失败返回 None
        """
        try:
            response = self.client.storage.from_(self.bucket_name).create_signed_url(
                path=file_path,
                expires_in=expires_in
            )
            return response.get('signedURL', '')
        except Exception as e:
            logger.error(f"[Supabase Storage] 获取文件 URL 失败: {file_path}, 错误: {str(e)}")
            return None
    
    def file_exists(self, file_path: str) -> bool:
        """
        检查文件是否存在
        
        Args:
            file_path: 文件路径
        
        Returns:
            是否存在
        """
        try:
            files = self.client.storage.from_(self.bucket_name).list(path=file_path)
            # 如果返回列表不为空，说明文件存在
            return len(files) > 0
        except Exception:
            return False


# 全局 Supabase Storage 实例
_supabase_storage: Optional[SupabaseStorage] = None


def get_supabase_storage() -> Optional[SupabaseStorage]:
    """
    获取全局 Supabase Storage 实例（单例）
    
    Returns:
        SupabaseStorage 实例，如果未配置则返回 None
    """
    global _supabase_storage
    
    # 如果未启用云存储模式，返回 None
    if config.STORAGE_MODE != "cloud":
        return None
    
    # 如果已创建实例，直接返回
    if _supabase_storage is not None:
        return _supabase_storage
    
    # 检查配置
    if not config.SUPABASE_URL or not config.SUPABASE_SERVICE_KEY:
        logger.warning("[Supabase Storage] 未配置 Supabase URL 或 Service Key，无法使用云存储")
        return None
    
    # 创建新实例
    try:
        _supabase_storage = SupabaseStorage()
        return _supabase_storage
    except Exception as e:
        logger.error(f"[Supabase Storage] 初始化失败: {str(e)}")
        return None

