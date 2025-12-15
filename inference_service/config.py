"""
Inference Service 配置
与 backend 平行的目录，通过环境变量控制模型与服务参数。
"""

import os
import sys
from pathlib import Path

# 将项目根目录加入 sys.path，以便复用 backend 的工具与配置
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

# 复用 backend 的通用配置（模型名称、下载源等）
from backend.utils.config import config as backend_config  # noqa: E402


class InferenceConfig:
    """推理服务配置"""

    # 服务基础配置
    HOST: str = os.getenv("INFERENCE_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("INFERENCE_PORT", "8001"))
    API_KEY: str = os.getenv("INFERENCE_API_KEY", "78tkUvoIzHRp68I0M97wePh1cbTxzzNu37i")
    LOG_LEVEL: str = os.getenv("INFERENCE_LOG_LEVEL", "info")
    REQUEST_TIMEOUT: float = float(os.getenv("INFERENCE_TIMEOUT", "30"))

    # 模型配置（默认复用 backend）
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", backend_config.EMBEDDING_MODEL)
    EMBEDDING_DEVICE: str = os.getenv("EMBEDDING_DEVICE", backend_config.EMBEDDING_DEVICE)
    NORMALIZE_EMBEDDINGS: bool = (
        os.getenv("NORMALIZE_EMBEDDINGS", "true").lower() == "true"
    )
    RERANKER_MODEL: str = os.getenv("RERANKER_MODEL", backend_config.RERANKER_MODEL)

    # 下载源：huggingface / modelscope，默认与 backend 保持一致
    MODEL_DOWNLOAD_SOURCE: str = os.getenv(
        "MODEL_DOWNLOAD_SOURCE", backend_config.MODEL_DOWNLOAD_SOURCE
    ).lower()


inference_config = InferenceConfig()

