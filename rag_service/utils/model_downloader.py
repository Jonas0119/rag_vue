"""
模型下载工具 - 从 ModelScope 下载模型到本地默认缓存目录
"""
import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def download_model_from_modelscope(model_name: str) -> str:
    """
    从 ModelScope 下载模型到默认缓存目录
    
    Args:
        model_name: 模型名称，如 'BAAI/bge-large-zh-v1.5'
    
    Returns:
        本地模型路径
    
    Raises:
        ImportError: 如果 modelscope 未安装
        Exception: 如果下载失败
    """
    try:
        from modelscope import snapshot_download
    except ImportError:
        raise ImportError(
            "ModelScope SDK 未安装。\n"
            "如果使用 Poetry 管理依赖，请运行: poetry install\n"
            "如果使用 pip，请运行: pip install modelscope\n"
            "或者检查 pyproject.toml 中是否包含 modelscope 依赖"
        )
    
    try:
        logger.info(f"[模型下载] 开始从 ModelScope 下载模型: {model_name}")
        
        # 使用 ModelScope SDK 下载模型到默认缓存目录
        # snapshot_download 会自动使用默认缓存目录（通常为 ~/.cache/modelscope/hub/）
        # 如果模型已存在，会直接返回路径，不会重复下载
        model_dir = snapshot_download(model_name)
        
        # 验证模型目录是否存在
        if not os.path.exists(model_dir):
            raise FileNotFoundError(f"模型下载后路径不存在: {model_dir}")
        
        logger.info(f"[模型下载] 模型下载完成: {model_name}, 本地路径: {model_dir}")
        return model_dir
        
    except Exception as e:
        logger.error(f"[模型下载] 从 ModelScope 下载模型失败: {model_name}, 错误: {str(e)}", exc_info=True)
        raise


def get_model_path(model_name: str, download_source: str = "modelscope") -> str:
    """
    获取模型路径，如果需要则从 ModelScope 下载
    
    Args:
        model_name: 模型名称，如 'BAAI/bge-large-zh-v1.5'
        download_source: 下载源，'modelscope' 或 'huggingface'
    
    Returns:
        模型路径（本地路径或 HuggingFace 模型名称）
    """
    if download_source == "modelscope":
        # 从 ModelScope 下载到本地
        return download_model_from_modelscope(model_name)
    else:
        # 使用 HuggingFace，直接返回模型名称
        return model_name

