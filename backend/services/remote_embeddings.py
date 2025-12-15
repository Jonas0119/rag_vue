"""
远程 Embeddings 适配器
通过 HTTP 将 embed 请求转发到外部推理服务（如 ngrok 暴露的 FastAPI）。
"""

import logging
from typing import List

import requests

from backend.utils.config import config

logger = logging.getLogger(__name__)


class RemoteEmbeddings:
    """实现 LangChain Embeddings 接口的远程调用版本。"""

    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        timeout: float = 15.0,
        max_retry: int = 2,
    ):
        if not base_url:
            raise ValueError("RemoteEmbeddings 需要配置 base_url")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retry = max_retry

    def _headers(self):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _request_embeddings(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        url = f"{self.base_url}/embed"
        payload = {
            "texts": texts,
            "normalize_embeddings": config.NORMALIZE_EMBEDDINGS,
        }
        last_err = None
        for attempt in range(self.max_retry + 1):
            try:
                resp = requests.post(
                    url, json=payload, headers=self._headers(), timeout=self.timeout
                )
                resp.raise_for_status()
                data = resp.json()
                if "embeddings" not in data:
                    raise ValueError(f"/embed 返回缺少 embeddings: {data}")
                return data["embeddings"]
            except Exception as e:
                last_err = e
                logger.warning(
                    "[RemoteEmbeddings] 请求失败（第 %s 次）：%s", attempt + 1, str(e)
                )
        raise RuntimeError(f"远程 embeddings 调用失败: {last_err}")

    # LangChain Embeddings 接口
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._request_embeddings(texts)

    def embed_query(self, text: str) -> List[float]:
        result = self._request_embeddings([text])
        return result[0] if result else []

