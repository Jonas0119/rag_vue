## rag_service（本地 RAG 服务）

### 职责

- **完整 RAG 工作流**：基于 LangChain + LangGraph 实现检索增强生成，包括检索、评估、重写、生成等节点。
- **向量库管理**：支持 Chroma（本地）与 Pinecone（云），每个用户独立 Collection。
- **文档处理**：从 Supabase Storage 或本地文件系统读取，解析 PDF/文本，清洗、分块（支持 Parent-Child），向量化并写入向量库与数据库。
- **模型加载**：启动时从 ModelScope（或 HuggingFace）下载并缓存 Embedding 模型与 CrossEncoder Reranker。
- **对外 API**：
  - `POST /api/chat/message`：对话接口，SSE 流式输出。
  - `POST /api/documents/{doc_id}/process`：触发文档处理。
  - `DELETE /api/documents/{doc_id}/delete-vectors`：删除某文档的向量数据。

### 目录结构

```text
rag_service/
  main.py                 # FastAPI 入口，预加载模型并挂载路由
  api/
    chat.py               # /api/chat/message（SSE）
    documents.py          # 文档处理与向量删除接口
  services/
    rag_service.py        # RAG 主服务，封装 LangGraph 与降级逻辑
    rag_graph.py          # LangGraph 图定义
    rag_state.py          # 图状态定义
    rag_nodes.py          # 各节点实现
    rag_tools.py          # 检索工具封装
    vector_store_service.py  # Embedding + 向量库策略（Chroma/Pinecone）
    vector_strategies.py  # 具体策略实现
    hybrid_retriever.py   # 混合检索
    reranker.py           # CrossEncoderReranker（本地模型）
    checkpoint_manager.py # LangGraph checkpoint
    document_processor.py # 文档解析/分块/向量化逻辑
  utils/
    config.py             # 配置与环境变量
    model_downloader.py   # 从 ModelScope 下载模型
    prompts.py            # 提示模板
    token_counter.py      # Token 统计
    text_splitter.py      # 文本分块
    document_cleaner.py   # 文本清洗
    parent_child_splitter.py # Parent-Child 分块
    supabase_storage.py   # Supabase Storage 封装
    file_handler.py       # 文件工具
  database/
    __init__.py           # 导出 DocumentDAO / SessionDAO / MessageDAO 等
    ...                   # 具体 DAO 与模型定义
  pyproject.toml          # rag_service 专用依赖
```

### 本地启动

```bash
cd rag_service
pip install .
uvicorn rag_service.main:app --host 0.0.0.0 --port 8001
```

启动时会自动：

- 通过 `model_downloader.get_model_path` 从 ModelScope 下载 Embedding 模型与 Reranker；
- 初始化向量库策略（本地 Chroma 或云端 Pinecone）；
- 在 `/` 与 `/health` 提供健康检查信息。

### 常用环境变量（示例）

```env
# LLM / API
ANTHROPIC_API_KEY=sk-xxx
ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic
LLM_MODEL=MiniMax-M2

# Embedding & Reranker
EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
EMBEDDING_DEVICE=cuda        # 或 cpu
NORMALIZE_EMBEDDINGS=true
RERANKER_MODEL=BAAI/bge-reranker-base
MODEL_DOWNLOAD_SOURCE=modelscope  # 或 huggingface

# 向量库
VECTOR_DB_MODE=cloud         # cloud: Pinecone, local: Chroma
PINECONE_API_KEY=...
PINECONE_ENVIRONMENT=...
PINECONE_INDEX_NAME=rag-system

# 存储与数据库
STORAGE_MODE=cloud           # cloud: Supabase Storage
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=your_publishable_key
SUPABASE_SERVICE_KEY=your_service_key
SUPABASE_STORAGE_BUCKET=rag
DATABASE_URL=postgresql://...

# Checkpoint / LangGraph
USE_CHECKPOINT=true
CHECKPOINT_DB_PATH=data/checkpoints/checkpoints.db

# 其他可选配置见 utils/config.py
```

详细的部署与运行方式见 `rag_service/DEPLOYMENT.md`。


