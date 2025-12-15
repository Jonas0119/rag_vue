import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

# 将项目根目录加入 sys.path，以便复用 backend 的工具与配置
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from backend.utils.model_downloader import get_model_path  # noqa: E402
from backend.utils.config import config as backend_config  # noqa: E402
from inference_service.config import inference_config  # noqa: E402
from langchain_huggingface import HuggingFaceEmbeddings  # noqa: E402
from sentence_transformers import CrossEncoder  # noqa: E402

logger = logging.getLogger(__name__)

app = FastAPI(title="Local Inference Service", version="0.1.0")


class EmbedRequest(BaseModel):
    texts: List[str] = Field(..., description="待编码的文本列表")
    normalize_embeddings: Optional[bool] = Field(
        None, description="是否归一化，缺省使用配置值"
    )


class EmbedResponse(BaseModel):
    embeddings: List[List[float]]
    model: str


class RerankDocument(BaseModel):
    id: Optional[str] = Field(None, description="文档标识（可选）")
    text: str = Field(..., description="文档内容")


class RerankRequest(BaseModel):
    query: str = Field(..., description="查询文本")
    documents: List[RerankDocument] = Field(..., description="待重排文档列表")
    top_n: int = Field(3, description="返回前多少条")
    score_threshold: Optional[float] = Field(
        None, description="分数阈值，低于阈值的文档会被过滤"
    )


class RerankResponseItem(BaseModel):
    id: Optional[str]
    score: float


class RerankResponse(BaseModel):
    results: List[RerankResponseItem]
    model: str


def require_api_key(authorization: str = Header(None)) -> None:
    """简单的 header 鉴权"""
    expected = inference_config.API_KEY
    if not expected:
        return
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization"
        )
    token = authorization.replace("Bearer ", "").strip()
    if token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )


# 模型全局缓存
embeddings_model: Optional[HuggingFaceEmbeddings] = None
reranker_model: Optional[CrossEncoder] = None


def _load_embeddings() -> HuggingFaceEmbeddings:
    global embeddings_model
    if embeddings_model is not None:
        return embeddings_model

    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    model_path = get_model_path(
        inference_config.EMBEDDING_MODEL, inference_config.MODEL_DOWNLOAD_SOURCE
    )
    logger.info(
        "[InferenceService] 加载 Embedding 模型: %s (source=%s)",
        model_path,
        inference_config.MODEL_DOWNLOAD_SOURCE,
    )
    embeddings_model = HuggingFaceEmbeddings(
        model_name=model_path,
        model_kwargs={"device": inference_config.EMBEDDING_DEVICE},
        encode_kwargs={"normalize_embeddings": inference_config.NORMALIZE_EMBEDDINGS},
    )
    logger.info("[InferenceService] Embedding 模型加载完成")
    return embeddings_model


def _load_reranker() -> CrossEncoder:
    global reranker_model
    if reranker_model is not None:
        return reranker_model

    model_path = get_model_path(
        inference_config.RERANKER_MODEL, inference_config.MODEL_DOWNLOAD_SOURCE
    )
    logger.info(
        "[InferenceService] 加载 Reranker 模型: %s (source=%s)",
        model_path,
        inference_config.MODEL_DOWNLOAD_SOURCE,
    )
    reranker_model = CrossEncoder(model_path)
    logger.info("[InferenceService] Reranker 模型加载完成")
    return reranker_model


@app.on_event("startup")
async def startup_event():
    logging.basicConfig(
        level=getattr(logging, inference_config.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    try:
        _load_embeddings()
        _load_reranker()
    except Exception:
        logger.exception("[InferenceService] 启动加载模型失败")
        # 不中断启动，让调用时再报错


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "embedding_loaded": embeddings_model is not None,
        "reranker_loaded": reranker_model is not None,
        "embedding_model": inference_config.EMBEDDING_MODEL,
        "reranker_model": inference_config.RERANKER_MODEL,
        "download_source": inference_config.MODEL_DOWNLOAD_SOURCE,
    }


@app.post("/embed", response_model=EmbedResponse, dependencies=[Depends(require_api_key)])
async def embed(req: EmbedRequest):
    model = _load_embeddings()
    try:
        normalize = (
            inference_config.NORMALIZE_EMBEDDINGS
            if req.normalize_embeddings is None
            else req.normalize_embeddings
        )
        # HuggingFaceEmbeddings 不暴露动态参数，这里手动规范化
        embeddings = model.embed_documents(req.texts)
        if normalize:
            import numpy as np

            embeddings = [
                (np.array(v) / (np.linalg.norm(v) + 1e-12)).tolist() for v in embeddings
            ]
        return EmbedResponse(embeddings=embeddings, model=inference_config.EMBEDDING_MODEL)
    except Exception as e:
        logger.exception("[InferenceService] /embed 调用失败")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/rerank", response_model=RerankResponse, dependencies=[Depends(require_api_key)]
)
async def rerank(req: RerankRequest):
    model = _load_reranker()
    if not req.documents:
        return RerankResponse(results=[], model=inference_config.RERANKER_MODEL)
    try:
        pairs = [[req.query, d.text] for d in req.documents]
        scores = model.predict(pairs)

        # 组合结果
        items = []
        for doc, score in zip(req.documents, scores):
            items.append(RerankResponseItem(id=doc.id, score=float(score)))

        # 排序 & 阈值过滤
        items.sort(key=lambda x: x.score, reverse=True)
        if req.score_threshold is not None:
            items = [it for it in items if it.score >= req.score_threshold]
        if req.top_n:
            items = items[: req.top_n]

        return RerankResponse(results=items, model=inference_config.RERANKER_MODEL)
    except Exception as e:
        logger.exception("[InferenceService] /rerank 调用失败")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(
        "inference_service.main:app",
        host=inference_config.HOST,
        port=inference_config.PORT,
        reload=False,
    )

