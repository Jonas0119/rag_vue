## rag_service 部署说明（本地/服务器 RAG 服务）

`rag_service` 负责完整的 RAG 工作流与文档处理，通常部署在你控制的机器或服务器上，通过 ngrok 或其他反向代理暴露为公网 HTTPS 地址，供 Vercel backend 调用。

---

### 1. 环境与依赖

#### Python 与依赖

- Python `>=3.10`
- 通过 `rag_service/pyproject.toml` 安装依赖：

```bash
cd rag_service
pip install .
```

（也可以使用 uv/pdm/poetry 等工具，根据你自己的偏好配置）

#### 硬件建议

- CPU 模式可以运行，但 Embedding 与 Reranker 首次加载较慢。
- 推荐使用带 GPU 的服务器（如 `EMBEDDING_DEVICE=cuda`），显著提升向量化与重排性能。

---

### 2. 环境变量配置

在 `rag_service` 目录下创建 `.env`（或使用系统环境变量）：

```env
# LLM / API
ANTHROPIC_API_KEY=sk-xxx
ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic
LLM_MODEL=MiniMax-M2

# Embedding & Reranker（从 ModelScope 下载）
EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
EMBEDDING_DEVICE=cuda        # 或 cpu
NORMALIZE_EMBEDDINGS=true
RERANKER_MODEL=BAAI/bge-reranker-base
MODEL_DOWNLOAD_SOURCE=modelscope

# 向量库
VECTOR_DB_MODE=cloud         # cloud: Pinecone, local: Chroma
PINECONE_API_KEY=...
PINECONE_ENVIRONMENT=...
PINECONE_INDEX_NAME=rag-system

# 存储与数据库（与 backend 共用）
STORAGE_MODE=cloud
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=your_publishable_key
SUPABASE_SERVICE_KEY=your_service_key
SUPABASE_STORAGE_BUCKET=rag
DATABASE_URL=postgresql://...

# Checkpoint / LangGraph
USE_CHECKPOINT=true
CHECKPOINT_DB_PATH=data/checkpoints/checkpoints.db

# 其他可选优化参数见 utils/config.py
```

---

### 3. 启动服务

本地或服务器上启动 FastAPI 应用：

```bash
cd rag_service
uvicorn rag_service.main:app --host 0.0.0.0 --port 8001
```

启动日志中可看到：

- Embedding 模型预加载状态；
- Reranker 模型加载状态；
- `/` 和 `/health` 提供的健康信息。

---

### 4. 通过 ngrok 暴露为公网地址

在本地或服务器上安装并启动 ngrok：

```bash
ngrok http 8001
```

得到类似地址：

```text
https://your-rag-service.ngrok-free.app
```

将该地址配置到 Vercel backend 的环境变量中：

```env
RAG_SERVICE_URL=https://your-rag-service.ngrok-free.app
```

backend 会通过此地址调用：

- `POST {RAG_SERVICE_URL}/api/chat/message`
- `POST {RAG_SERVICE_URL}/api/documents/{doc_id}/process`
- `DELETE {RAG_SERVICE_URL}/api/documents/{doc_id}/delete-vectors`

---

### 5. 手动验证 API

启动服务后，可以直接使用 curl/Postman 调试：

- 健康检查：

```bash
curl http://localhost:8001/health
```

- 文档处理（示例）：

```bash
curl -X POST "http://localhost:8001/api/documents/your-doc-id/process" \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "your-doc-id",
    "user_id": 1,
    "filepath": "user_1/your-file.pdf",
    "file_type": ".pdf"
  }'
```

- 聊天接口（简单示例，未展示 SSE 解析）：

```bash
curl -N -X POST "http://localhost:8001/api/chat/message" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "你好，帮我总结一下这个文档的要点？",
    "user_id": 1
  }'
```

---

### 6. 运维与监控建议

- 为 `rag_service` 添加外部监控（如 Prometheus + Grafana 或简单的心跳检测）：
  - 定期访问 `/health`，检查模型加载与服务状态。
- 对模型与向量库操作增加基本日志与错误告警：
  - 超时、Pinecone/数据库错误应记录并可观测。
- 注意 ModelScope 下载缓存目录（通常在 `~/.cache/modelscope`），必要时做磁盘容量监控。

---

更多与 backend/前端协同的整体部署流程，请参考项目根目录的 `DEPLOYMENT.md`。 


