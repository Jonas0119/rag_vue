"""
文件处理工具 - 支持本地文件系统和 Supabase Storage
"""
import os
from pathlib import Path
from typing import Optional, Tuple
import hashlib
import logging

from backend.utils.config import config

logger = logging.getLogger(__name__)


ALLOWED_EXTENSIONS = {'.pdf', '.txt', '.md', '.docx'}


def get_file_extension(filename: str) -> str:
    """获取文件扩展名"""
    return Path(filename).suffix.lower()


def is_allowed_file(filename: str) -> bool:
    """检查文件类型是否允许"""
    ext = get_file_extension(filename)
    return ext in ALLOWED_EXTENSIONS


def validate_file_size(file_size: int, max_size: int) -> Tuple[bool, str]:
    """
    验证文件大小
    
    Returns:
        (是否有效, 错误信息)
    """
    if file_size > max_size:
        max_mb = max_size / (1024 * 1024)
        return False, f"文件过大，最大支持 {max_mb:.1f} MB"
    return True, ""


def generate_safe_filename(original_filename: str) -> str:
    """
    生成安全的文件名（使用 hash）
    
    Args:
        original_filename: 原始文件名
    
    Returns:
        安全的文件名（保留扩展名）
    """
    ext = get_file_extension(original_filename)
    # 使用时间戳 + 文件名的 hash
    import time
    timestamp = str(int(time.time()))
    hash_value = hashlib.md5(original_filename.encode()).hexdigest()[:8]
    return f"{timestamp}_{hash_value}{ext}"


def format_file_size(size_bytes: int) -> str:
    """
    格式化文件大小
    
    Args:
        size_bytes: 文件大小（字节）
    
    Returns:
        格式化后的字符串（如：1.5 MB）
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def ensure_directory_exists(directory: str):
    """确保目录存在（仅在本地模式下）"""
    # 在云模式下，不应该创建本地目录
    if config.STORAGE_MODE == "cloud":
        logger.warning(f"[文件处理] 云模式下跳过目录创建: {directory}")
        return
    Path(directory).mkdir(parents=True, exist_ok=True)


def save_uploaded_file(uploaded_file, save_path: str, user_id: Optional[int] = None) -> bool:
    """
    保存上传的文件（支持本地和云存储）
    
    Args:
        uploaded_file: Streamlit UploadedFile 对象
        save_path: 保存路径（本地模式）或文件路径（云模式，格式：user_{user_id}/{filename}）
        user_id: 用户 ID（云模式必需）
    
    Returns:
        是否成功
    """
    if config.STORAGE_MODE == "cloud":
        # 使用 Supabase Storage
        from backend.utils.supabase_storage import get_supabase_storage
        
        storage = get_supabase_storage()
        if storage is None:
            logger.error("[文件处理] Supabase Storage 未初始化")
            return False
        
        # 如果 save_path 已经是云存储路径格式（user_{user_id}/{filename}），直接使用
        # 否则，如果 save_path 是本地路径，需要转换为云存储路径
        if user_id is None:
            logger.error("[文件处理] 云存储模式需要提供 user_id")
            return False
        
        # 判断 save_path 是否已经是云存储路径格式
        if save_path.startswith(f"user_{user_id}/"):
            # 已经是云存储路径格式，直接使用
            cloud_path = save_path
        else:
            # 是本地路径，提取文件名并构建云存储路径
            filename = Path(save_path).name
            cloud_path = f"user_{user_id}/{filename}"
        
        # 上传到 Supabase Storage
        # 读取文件数据为 bytes（而不是使用 getbuffer() 返回的 memoryview）
        uploaded_file.seek(0)  # 确保从文件开头读取
        file_data = uploaded_file.read()  # 直接读取为 bytes
        success, _ = storage.upload_file(file_data, cloud_path)
        return success
    else:
        # 使用本地文件系统（原有逻辑）
        try:
            # 确保目录存在
            ensure_directory_exists(Path(save_path).parent)
            
            # 保存文件
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            return True
        except Exception as e:
            logger.error(f"[文件处理] 保存文件失败: {e}")
            return False


def delete_file(file_path: str) -> bool:
    """
    删除文件（支持本地和云存储）
    
    Args:
        file_path: 文件路径（本地模式）或云存储路径（云模式）
    
    Returns:
        是否成功
    """
    if config.STORAGE_MODE == "cloud":
        # 使用 Supabase Storage
        from backend.utils.supabase_storage import get_supabase_storage
        
        storage = get_supabase_storage()
        if storage is None:
            logger.error("[文件处理] Supabase Storage 未初始化")
            return False
        
        # file_path 应该是云存储路径格式（user_{user_id}/{filename}）
        # 如果传入的是本地路径，需要转换（但通常不会发生，因为数据库存储的是云路径）
        # 这里假设 file_path 已经是云存储路径格式
        return storage.delete_file(file_path)
    else:
        # 使用本地文件系统（原有逻辑）
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            return True
        except Exception as e:
            logger.error(f"[文件处理] 删除文件失败: {e}")
            return False


def read_text_file(file_path: str) -> Optional[str]:
    """
    读取文本文件（支持本地和云存储）
    
    Args:
        file_path: 文件路径（本地模式）或云存储路径（云模式）
    
    Returns:
        文件内容，失败返回 None
    """
    if config.STORAGE_MODE == "cloud":
        # 使用 Supabase Storage
        from backend.utils.supabase_storage import get_supabase_storage
        
        storage = get_supabase_storage()
        if storage is None:
            logger.error("[文件处理] Supabase Storage 未初始化")
            return None
        
        # 下载文件
        file_data = storage.download_file(file_path)
        if file_data is None:
            return None
        
        # 尝试解码为文本
        try:
            return file_data.decode('utf-8')
        except UnicodeDecodeError:
            try:
                return file_data.decode('gbk')
            except Exception:
                return None
    else:
        # 使用本地文件系统（原有逻辑）
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # 尝试其他编码
            try:
                with open(file_path, 'r', encoding='gbk') as f:
                    return f.read()
            except Exception:
                return None
        except Exception as e:
            logger.error(f"[文件处理] 读取文件失败: {e}")
            return None


def read_file_bytes(file_path: str) -> Optional[bytes]:
    """
    读取文件二进制数据（支持本地和云存储）
    
    Args:
        file_path: 文件路径（本地模式）或云存储路径（云模式）
    
    Returns:
        文件二进制数据，失败返回 None
    """
    if config.STORAGE_MODE == "cloud":
        # 使用 Supabase Storage
        from backend.utils.supabase_storage import get_supabase_storage
        
        storage = get_supabase_storage()
        if storage is None:
            logger.error("[文件处理] Supabase Storage 未初始化")
            return None
        
        return storage.download_file(file_path)
    else:
        # 使用本地文件系统
        try:
            with open(file_path, 'rb') as f:
                return f.read()
        except Exception as e:
            logger.error(f"[文件处理] 读取文件失败: {e}")
            return None

