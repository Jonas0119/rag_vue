"""
Reranker 模块
使用 Cross-Encoder 对初步检索结果进行重排序
"""

import logging
from typing import List, Optional, Dict

import requests
from langchain_core.documents import Document

from rag_service.utils.config import config
from rag_service.utils.model_downloader import get_model_path

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """使用 Cross-Encoder 对候选文档进行重排序的简单封装。"""

    def __init__(self, model_name: str = None, use_modelscope: bool = True):
        """
        初始化 Reranker

        Args:
            model_name: Cross-Encoder 模型名称，如果为 None 则使用配置中的 RERANKER_MODEL
            use_modelscope: 是否使用 ModelScope 下载模型（避免 HuggingFace 连接问题）
        """
        self.model = None
        # 如果未指定模型名称，使用配置中的默认值（中文专用模型）
        if model_name is None:
            model_name = config.RERANKER_MODEL
        # 懒加载 sentence-transformers，避免在未安装时导入失败
        try:
            from sentence_transformers import CrossEncoder  # type: ignore[import]
        except Exception as e:
            logger.error(
                "[Reranker] sentence-transformers 未安装，无法使用本地 CrossEncoderReranker。"
            )
            raise ImportError(
                "sentence-transformers 未安装，本地 CrossEncoderReranker 不可用。"
                "如果需要在本地加载 rerank 模型，请安装 sentence-transformers。"
            ) from e

        # 优先使用配置的下载源
        download_source = config.MODEL_DOWNLOAD_SOURCE if use_modelscope else "huggingface"
        
        try:
            model_path = get_model_path(model_name, download_source)
            logger.info(f"[Reranker] 正在加载模型: {model_path} (source={download_source})")
            self.model = CrossEncoder(model_path)
            logger.info("[Reranker] 模型加载完成")
        except Exception as e:
            logger.error(f"[Reranker] 模型加载失败: {str(e)}")
            # 如果 ModelScope 下载失败，尝试回退到 HuggingFace
            if download_source == "modelscope":
                logger.warning("[Reranker] ModelScope 下载失败，尝试使用 HuggingFace")
                try:
                    model_path = get_model_path(model_name, "huggingface")
                    self.model = CrossEncoder(model_path)
                    logger.info("[Reranker] 使用 HuggingFace 成功加载模型")
                except Exception as e2:
                    logger.error(f"[Reranker] HuggingFace 加载也失败: {str(e2)}")
                    raise e  # 抛出原始错误
            else:
                raise

    def rerank(
        self, 
        query: str, 
        documents: List[Document], 
        top_n: int = 3,
        score_threshold: Optional[float] = None
    ) -> List[Document]:
        """
        根据查询对候选文档进行重排序并返回前 top_n（可选：根据阈值过滤）

        Args:
            query: 查询文本
            documents: 初步检索得到的候选文档列表
            top_n: 返回的文档数量上限
            score_threshold: 相关性分数阈值，低于此分数的文档将被过滤掉（None 表示不过滤）

        Returns:
            排序后的文档列表（可能少于 top_n，如果设置了阈值）
        """
        if not documents:
            return []

        pairs = [[query, doc.page_content] for doc in documents]  # 为每个文档构造 (query, 文档内容) 对
        scores = self.model.predict(pairs)  # 使用模型预测每对的相关性分数

        # 将分数写回 metadata，便于调试/展示
        for doc, score in zip(documents, scores):   # 遍历文档和对应的分数
            doc.metadata = dict(doc.metadata or {})  # 确保 metadata 是一个 dict（防止为 None）
            doc.metadata["rerank_score"] = float(score)  # 写入 rerank 得分到 metadata

        # 按分数降序排序
        sorted_docs = sorted(
            documents, 
            key=lambda d: d.metadata.get("rerank_score", 0),
            reverse=True,
        )
        
        # 如果设置了阈值，过滤掉低于阈值的文档
        if score_threshold is not None:
            filtered_docs = [
                doc for doc in sorted_docs 
                if doc.metadata.get("rerank_score", 0) >= score_threshold
            ]
            # 返回过滤后的文档（不超过 top_n）
            return filtered_docs[:top_n]
        else:
            # 没有阈值，直接返回前 top_n
            return sorted_docs[:top_n]


class RemoteReranker:
    """通过远程推理服务进行重排的封装。"""

    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        timeout: float = 15.0,
        max_retry: int = 2,
    ):
        if not base_url:
            raise ValueError("RemoteReranker 需要配置 base_url")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retry = max_retry
        self.logger = logging.getLogger(__name__)

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def rerank(
        self,
        query: str,
        documents: List[Document],
        top_n: int = 3,
        score_threshold: Optional[float] = None,
    ) -> List[Document]:
        if not documents:
            return []

        doc_payload = []
        id_to_doc: Dict[str, Document] = {}
        for idx, doc in enumerate(documents):
            doc_id = str(
                doc.metadata.get("doc_id")
                or doc.metadata.get("source")
                or doc.metadata.get("id")
                or idx
            )
            id_to_doc[doc_id] = doc
            doc_payload.append({"id": doc_id, "text": doc.page_content})

        payload = {
            "query": query,
            "documents": doc_payload,
            "top_n": top_n,
            "score_threshold": score_threshold,
        }

        last_err = None
        url = f"{self.base_url}/rerank"
        for attempt in range(self.max_retry + 1):
            try:
                resp = requests.post(
                    url, json=payload, headers=self._headers(), timeout=self.timeout
                )
                resp.raise_for_status()
                data = resp.json()
                results = data.get("results", [])
                for item in results:
                    doc_id = str(item.get("id"))
                    score = float(item.get("score", 0))
                    doc = id_to_doc.get(doc_id)
                    if doc is None:
                        continue
                    doc.metadata = dict(doc.metadata or {})
                    doc.metadata["rerank_score"] = score

                # 过滤掉未被远程返回的文档
                scored_docs = [d for d in documents if "rerank_score" in d.metadata]
                scored_docs.sort(
                    key=lambda d: d.metadata.get("rerank_score", 0), reverse=True
                )
                if score_threshold is not None:
                    scored_docs = [
                        d
                        for d in scored_docs
                        if d.metadata.get("rerank_score", 0) >= score_threshold
                    ]
                return scored_docs[:top_n]
            except Exception as e:
                last_err = e
                self.logger.warning(
                    "[RemoteReranker] 请求失败（第 %s 次）：%s", attempt + 1, str(e)
                )
        raise RuntimeError(f"远程 rerank 调用失败: {last_err}")


