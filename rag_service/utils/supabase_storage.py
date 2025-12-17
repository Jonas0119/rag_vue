"""
Supabase Storage 封装
"""
from typing import Optional, Tuple
import logging
import time
from supabase import create_client, Client

from rag_service.utils.config import config
from rag_service.utils.performance_monitor import monitor_storage

logger = logging.getLogger(__name__)


class SupabaseStorage:
    """Supabase Storage 客户端"""
    
    def __init__(self):
        """初始化 Supabase Storage 客户端"""
        if not config.SUPABASE_URL or not config.SUPABASE_SERVICE_KEY:
            raise ValueError("Supabase URL 和 Service Key 必须配置")
        
        # 确保 SUPABASE_URL 以斜杠结尾（Supabase 客户端要求）
        supabase_url = config.SUPABASE_URL.rstrip('/') + '/'
        
        self.client: Client = create_client(
            supabase_url,
            config.SUPABASE_SERVICE_KEY  # 使用 Service Key 有完整权限
        )
        self.bucket_name = config.SUPABASE_STORAGE_BUCKET
    
    def upload_file(self, file_data: bytes, file_path: str, content_type: str = "application/octet-stream") -> Tuple[bool, str]:
        """
        上传文件到 Supabase Storage（支持大文件分块上传）
        
        Args:
            file_data: 文件二进制数据
            file_path: 文件路径（格式：user_{user_id}/{filename}）
            content_type: 文件 MIME 类型
        
        Returns:
            (是否成功, 文件路径或错误信息)
        """
        file_size = len(file_data)
        details = f"size={file_size} bytes, path={file_path}"
        
        # Supabase Storage 单次上传限制通常是 5-10MB，超过此大小需要使用分块上传
        CHUNK_SIZE_THRESHOLD = 5 * 1024 * 1024  # 5MB
        
        with monitor_storage("upload_file", details):
            try:
                # 对于大文件，使用 io.BytesIO 包装并尝试上传
                # 如果仍然失败，则使用 HTTP 直接上传（分块）
                if file_size > CHUNK_SIZE_THRESHOLD:
                    # 尝试使用 io.BytesIO 包装数据
                    import io
                    file_obj = io.BytesIO(file_data)
                    upload_start = time.time()
                    try:
                        response = self.client.storage.from_(self.bucket_name).upload(
                            path=file_path,
                            file=file_obj,
                            file_options={
                                "content-type": content_type,
                                "upsert": "false"
                            }
                        )
                        logger.info(f"[Supabase Storage] 大文件上传成功（使用 BytesIO）: {file_path}, 大小: {file_size} bytes")
                        return True, file_path
                    except Exception as bytesio_error:
                        # BytesIO 方式失败，尝试使用 TUS 分块上传
                        # 优先使用 TUS 协议（推荐用于大文件）
                        tus_result = self._upload_large_file_tus(file_data, file_path, content_type)
                        if tus_result[0]:
                            return tus_result
                        # 如果 TUS 失败，降级到 HTTP 直接上传（可能仍然失败，但尝试一下）
                        logger.warning(f"[Supabase Storage] TUS 上传失败，尝试 HTTP 直接上传: {tus_result[1]}")
                        return self._upload_large_file_http(file_data, file_path, content_type)
                else:
                    # 小文件，使用原来的方式
                    upload_start = time.time()
                    response = self.client.storage.from_(self.bucket_name).upload(
                        path=file_path,
                        file=file_data,
                        file_options={
                            "content-type": content_type,
                            "upsert": "false"
                        }
                    )
                    logger.info(f"[Supabase Storage] 文件上传成功: {file_path}")
                    return True, file_path
            except Exception as e:
                error_msg = str(e)
                logger.error(f"[Supabase Storage] 文件上传失败: {file_path}, 错误: {error_msg}")
                return False, error_msg
    
    def _upload_large_file_tus(self, file_data: bytes, file_path: str, content_type: str) -> Tuple[bool, str]:
        """
        使用 TUS 协议进行大文件分块上传
        
        Args:
            file_data: 文件二进制数据
            file_path: 文件路径
            content_type: 文件 MIME 类型
        
        Returns:
            (是否成功, 文件路径或错误信息)
        """
        try:
            from tusclient import client as tus_client
            
            # 构建 TUS 上传端点
            # Supabase Storage TUS 端点格式：{SUPABASE_URL}/storage/v1/upload/resumable
            # 确保 URL 格式正确（移除尾部斜杠，因为路径以 / 开头）
            supabase_url = config.SUPABASE_URL.rstrip('/')
            tus_endpoint = f"{supabase_url}/storage/v1/upload/resumable"
            
            # 准备请求头（authorization 应该在 headers 中，而不是 metadata 中）
            headers = {
                "Authorization": f"Bearer {config.SUPABASE_SERVICE_KEY}",
                "apikey": config.SUPABASE_SERVICE_KEY,
                "x-upsert": "false"
            }
            
            # 准备元数据（TUS 协议格式）
            metadata = {
                "bucketName": self.bucket_name,
                "objectName": file_path,
                "contentType": content_type
            }
            
            # 创建 TUS 客户端（传入 headers）
            client = tus_client.TusClient(tus_endpoint, headers=headers)
            
            # tuspy 需要文件路径，不能直接使用 BytesIO
            # 将 bytes 数据写入临时文件
            import tempfile
            import os
            
            # 创建临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix='.tmp') as tmp_file:
                tmp_file.write(file_data)
                tmp_file_path = tmp_file.name
            
            try:
                # 打开文件对象用于上传
                # tuspy 的 uploader 需要文件对象，而不是文件路径
                with open(tmp_file_path, 'rb') as file_stream:
                    # 创建上传器（使用 6MB 块大小，这是 Supabase 推荐的）
                    uploader = client.uploader(
                        file_stream=file_stream,
                        chunk_size=6 * 1024 * 1024,  # 6MB chunks
                        metadata=metadata
                    )
                    
                    # 执行上传
                    uploader.upload()
                    logger.info(f"[Supabase Storage] 大文件 TUS 上传成功: {file_path}, 大小: {len(file_data)} bytes")
                    return True, file_path
            finally:
                # 清理临时文件
                try:
                    if os.path.exists(tmp_file_path):
                        os.unlink(tmp_file_path)
                except Exception as cleanup_error:
                    logger.warning(f"[Supabase Storage] 清理临时文件失败: {cleanup_error}")
            
        except ImportError:
            error_msg = "使用 TUS 上传需要安装 tuspy: pip install tuspy"
            logger.error(f"[Supabase Storage] {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = str(e)
            
            # 检查是否是 413 错误（文件大小限制）
            if "413" in error_msg or "Payload too large" in error_msg or "exceeded the maximum" in error_msg:
                detailed_error = (
                    f"文件大小超过 Supabase Storage 限制。"
                    f"文件大小: {len(file_data) / (1024*1024):.2f} MB。"
                    f"请检查："
                    f"1. Supabase Dashboard -> Storage Settings -> Global file size limit（免费版最大 50MB）"
                    f"2. Storage Buckets -> {self.bucket_name} -> Edit bucket -> Restrict file size"
                    f"3. 确保限制值大于文件大小"
                )
                logger.error(f"[Supabase Storage] TUS 上传失败（文件大小限制）: {detailed_error}")
                return False, detailed_error
            else:
                logger.error(f"[Supabase Storage] TUS 上传异常: {error_msg}")
                return False, f"TUS 上传失败: {error_msg}"
    
    def _upload_large_file_http(self, file_data: bytes, file_path: str, content_type: str) -> Tuple[bool, str]:
        """
        使用 HTTP 请求直接上传大文件
        
        Args:
            file_data: 文件二进制数据
            file_path: 文件路径
            content_type: 文件 MIME 类型
        
        Returns:
            (是否成功, 文件路径或错误信息)
        """
        try:
            from urllib.request import Request, urlopen
            from urllib.error import HTTPError, URLError
            import json as json_lib
            
            # 构建上传 URL（使用 S3 兼容的 PUT 端点，支持大文件）
            # 注意：需要 URL 编码文件路径
            from urllib.parse import quote
            encoded_path = quote(file_path, safe='')
            # 使用 S3 兼容端点：/storage/v1/object/sign/{bucket}/{path}
            # 或者直接使用：/storage/v1/object/{bucket}/{path} 配合 PUT 方法
            # 确保 URL 格式正确（移除尾部斜杠，因为路径以 / 开头）
            supabase_url = config.SUPABASE_URL.rstrip('/')
            upload_url = f"{supabase_url}/storage/v1/object/{self.bucket_name}/{encoded_path}"
            
            # 准备请求头（S3 兼容上传需要特定的头部）
            headers = {
                "Authorization": f"Bearer {config.SUPABASE_SERVICE_KEY}",
                "Content-Type": content_type,
                "apikey": config.SUPABASE_SERVICE_KEY,
                "x-upsert": "false"
            }
            
            # 执行上传（使用 PUT 方法，S3 兼容，支持大文件）
            upload_start = time.time()
            req = Request(upload_url, data=file_data, headers=headers, method="PUT")
            
            try:
                with urlopen(req, timeout=300) as response:
                    status_code = response.getcode()
                    response_body = response.read().decode('utf-8', errors='ignore')[:200]
                    
                    if status_code in [200, 201]:
                        logger.info(f"[Supabase Storage] 大文件 HTTP 上传成功: {file_path}, 大小: {len(file_data)} bytes")
                        return True, file_path
                    else:
                        error_msg = f"HTTP 上传失败: {status_code} - {response_body}"
                        logger.error(f"[Supabase Storage] {error_msg}")
                        return False, error_msg
            except HTTPError as e:
                error_body = e.read().decode('utf-8', errors='ignore')[:200] if hasattr(e, 'read') else str(e)
                error_msg = f"HTTP 上传失败: {e.code} - {e.reason} - {error_body}"
                logger.error(f"[Supabase Storage] {error_msg}")
                return False, error_msg
            except URLError as e:
                error_msg = f"URL 错误: {str(e)}"
                logger.error(f"[Supabase Storage] {error_msg}")
                return False, error_msg
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[Supabase Storage] HTTP 上传异常: {error_msg}")
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

