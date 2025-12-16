## Backend（Vercel 轻量网关）

### 职责

- **用户管理**：注册、登录、获取当前用户（`api/auth.py`、`services/user_service.py`）。
- **文档元数据管理**：上传文件到 Supabase Storage、记录/查询/删除文档元数据（`api/documents.py`、`services/document_service.py`），不负责解析/分块/向量化。
- **会话与消息管理**：创建/删除会话、查询历史消息（`api/sessions.py`、`services/session_service.py`）。
- **RAG 请求代理**：
  - `POST /api/chat/message` → 转发到 `{RAG_SERVICE_URL}/api/chat/message`（SSE 流式响应）。
  - `POST /api/documents/{doc_id}/process` → 转发到 `{RAG_SERVICE_URL}/api/documents/{doc_id}/process`。
  - 文档删除时调用 `{RAG_SERVICE_URL}/api/documents/{doc_id}/delete-vectors` 删除向量。

所有检索、重排、向量库和 LangGraph 逻辑均在 `rag_service` 中实现，backend 只做网关。

### 依赖

backend 使用独立的 `pyproject.toml`，只包含轻量依赖：

- **FastAPI & Serverless**
  - `fastapi`, `uvicorn[standard]`, `mangum`
- **配置与校验**
  - `pydantic[email]`, `pydantic-settings`, `python-multipart`, `python-dotenv`, `email-validator`
- **认证与安全**
  - `bcrypt`, `pyjwt`
- **存储与数据库**
  - `supabase`, `tuspy`, `psycopg2-binary`, `pypdf`（仅用于文件类型验证）
- **HTTP 客户端**
  - `httpx`（用于将聊天与文档处理请求代理到 `rag_service`）

### 本地启动

```bash
cd backend
pip install .  # 或使用 uv / pdm 等安装依赖
uvicorn main:app --reload
```

本地开发时需要：

- 正确配置数据库（可使用本地 SQLite 或 Supabase Postgres）。
- 配置 `RAG_SERVICE_URL` 指向本地或远程的 `rag_service`（例如通过 ngrok 暴露的地址）。

### 环境变量（示例）

```env
# 数据库
DATABASE_URL=postgresql://...

# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=your_publishable_key
SUPABASE_SERVICE_KEY=your_service_key
SUPABASE_STORAGE_BUCKET=rag

# JWT
JWT_SECRET_KEY=your_random_secret_key
JWT_EXPIRY_DAYS=30
JWT_ALGORITHM=HS256

# CORS
CORS_ORIGINS=https://your-frontend-domain.vercel.app

# RAG 服务地址（通过 ngrok 暴露的 rag_service）
RAG_SERVICE_URL=https://your-rag-service.ngrok-free.app
```

更多部署细节见 `backend/DEPLOYMENT.md`。


