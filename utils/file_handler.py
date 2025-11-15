"""
文件处理工具
"""
import os
from pathlib import Path
from typing import Optional, Tuple
import hashlib


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
    """确保目录存在"""
    Path(directory).mkdir(parents=True, exist_ok=True)


def save_uploaded_file(uploaded_file, save_path: str) -> bool:
    """
    保存上传的文件
    
    Args:
        uploaded_file: Streamlit UploadedFile 对象
        save_path: 保存路径
    
    Returns:
        是否成功
    """
    try:
        # 确保目录存在
        ensure_directory_exists(Path(save_path).parent)
        
        # 保存文件
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        return True
    except Exception as e:
        print(f"保存文件失败: {e}")
        return False


def delete_file(file_path: str) -> bool:
    """
    删除文件
    
    Args:
        file_path: 文件路径
    
    Returns:
        是否成功
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
        return True
    except Exception as e:
        print(f"删除文件失败: {e}")
        return False


def read_text_file(file_path: str) -> Optional[str]:
    """
    读取文本文件
    
    Args:
        file_path: 文件路径
    
    Returns:
        文件内容，失败返回 None
    """
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
        print(f"读取文件失败: {e}")
        return None

