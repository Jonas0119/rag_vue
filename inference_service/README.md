# Inference Service（FastAPI + ngrok）

本目录提供本地推理服务，将原本 backend 内的 embedding / rerank 模型下载与加载迁移到此，通过 HTTP 暴露接口并可用 ngrok 对外提供给 Vercel。

## 接口
- `GET /health` 健康检查
- `POST /embed` 入参 `{"texts": [...], "normalize_embeddings": true|false?}`，返回 `{"embeddings": [[...]], "model": "..."}`。
- `POST /rerank` 入参 `{"query": "...", "documents": [{"id":"1","text":"..."}, ...], "top_n":3, "score_threshold":0.1?}`，返回 `{"results":[{"id":"1","score":0.9},...], "model":"..."}`。

鉴权：如设置 `INFERENCE_API_KEY`，需在请求头 `Authorization: Bearer <token>`。

## 启动（统一使用 Poetry）
```bash
# 在项目根目录（含 pyproject.toml）
poetry install
poetry run uvicorn inference_service.main:app --host 0.0.0.0 --port 8001
```

## ngrok 暴露示例
```bash
ngrok http 8001
# 公网 URL 例如：https://nonanesthetized-nolan-riantly.ngrok-free.dev
```

将得到的 URL 配置到 backend 环境变量 `INFERENCE_API_BASE_URL`，同时设置 `USE_REMOTE_EMBEDDINGS=true` / `USE_REMOTE_RERANKER=true`。

