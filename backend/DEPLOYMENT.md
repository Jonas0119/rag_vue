## Backend 部署说明（Vercel 轻量网关）

backend 作为部署在 Vercel 的 Serverless API，仅负责：

- 用户、文档元数据、会话管理；
- 将聊天与文档处理请求代理到本地/远程的 `rag_service`。

RAG 相关依赖与模型均不在 Vercel 中部署。

---

## 目录

- [本地开发环境搭建](#本地开发环境搭建)
- [Vercel 部署](#vercel-部署)
- [环境变量配置](#环境变量配置)
- [故障排查](#故障排查)

---

## 本地开发环境搭建

### 1. 创建独立虚拟环境

**重要**: Backend 必须使用独立的虚拟环境，避免与 `rag_service` 的依赖冲突。

```bash
# 进入项目根目录
cd /path/to/rag_vue

# 创建 backend 专用虚拟环境
python3 -m venv backend/venv

# 激活虚拟环境
# macOS/Linux:
source backend/venv/bin/activate
# Windows:
# backend\venv\Scripts\activate
```

### 2. 安装依赖

```bash
# 确保在 backend 目录下
cd backend

# 升级 pip
pip install --upgrade pip

# 安装依赖
pip install .
```

### 3. 验证依赖安装

```bash
# 检查关键依赖
python -c "import fastapi; import httpx; import supabase; print('✅ 依赖安装成功')"

# 验证没有不应该存在的依赖（如 langchain）
python -c "import langchain_core" 2>/dev/null && echo "❌ 发现 langchain_core（不应该存在）" || echo "✅ 无 langchain 依赖"
```

### 4. 配置环境变量

```bash
# 复制配置模板
cp config_template.txt .env

# 编辑 .env 文件，至少配置以下变量：
# - DATABASE_URL: 数据库连接字符串
# - SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_KEY: Supabase 配置
# - JWT_SECRET_KEY: JWT 密钥
# - RAG_SERVICE_URL: RAG 服务地址（本地: http://localhost:8001）
```

### 5. 启动开发服务器

```bash
# 方式1: 使用 uvicorn 直接启动（推荐）
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 方式2: 使用 run.py
python run.py

# 方式3: 使用 Python 模块方式
python -m uvicorn main:app --reload
```

### 6. 验证服务

```bash
# 健康检查
curl http://localhost:8000/health

# 访问 API 文档
# 浏览器打开: http://localhost:8000/docs
```

### 7. 开发注意事项

- **环境隔离**: 确保使用独立的虚拟环境，不要与 `rag_service` 共享
- **依赖检查**: 如果遇到 `ModuleNotFoundError`，检查是否误用了 `rag_service` 的依赖
- **RAG Service**: 本地开发时需要同时运行 `rag_service`（端口 8001）

---

## Vercel 部署

### 1. 部署前准备

1. 已部署或可本地启动的 `rag_service`，并通过 ngrok 或其他反向代理暴露为公网 HTTPS 地址，例如：
   - `https://your-rag-service.ngrok-free.app`
2. Supabase / 数据库 / 向量库等已按 `rag_service` 要求配置好。

---

### 2. Vercel 项目配置

在 Vercel 中创建后端项目时，按如下配置：

- **Root Directory**: `backend`
- **Framework Preset**: `Other`
- **Build Command**: 安装依赖即可，例如：

  ```bash
  pip install .
  ```

- **Output Directory**: 不需要配置。

Vercel 会读取 `backend/vercel.json`，将 FastAPI 应用通过 Mangum 适配为 Serverless Functions。

---

### 3. 环境变量

在 Vercel 项目设置中添加以下环境变量（Production / Preview / Development 环境保持一致）：

- 基础配置

```env
DATABASE_URL=postgresql://...
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=your_publishable_key
SUPABASE_SERVICE_KEY=your_service_key
SUPABASE_STORAGE_BUCKET=rag
```

- 认证配置

```env
JWT_SECRET_KEY=your_random_secret_key
JWT_EXPIRY_DAYS=30
JWT_ALGORITHM=HS256
```

- CORS 配置

```env
CORS_ORIGINS=https://your-frontend-domain.vercel.app
```

- RAG 服务地址（必须）

```env
RAG_SERVICE_URL=https://your-rag-service.ngrok-free.app
```

`RAG_SERVICE_URL` 会被：

- `api/chat.py` 用于将 `POST /api/chat/message` 转发到 `rag_service`；
- `api/documents.py` 用于将文档处理与向量删除请求转发到 `rag_service`。

---

### 4. 首次部署与验证

1. 在本地或服务器上启动 `rag_service` 并通过 ngrok 暴露：

   ```bash
   cd rag_service
   pip install .
   uvicorn rag_service.main:app --host 0.0.0.0 --port 8001

   ngrok http 8001
   # 得到 https://your-rag-service.ngrok-free.app
   ```

2. 将上述地址填入 Vercel backend 的 `RAG_SERVICE_URL` 环境变量。

3. 在 Vercel 中触发构建与部署，观察日志确保依赖安装与启动正常。

4. 部署完成后，验证以下接口：
   - `GET /api/auth/me`：用户信息获取；
   - `GET /api/documents`：文档列表；
   - `POST /api/documents/upload`：上传文档；
   - `POST /api/documents/{doc_id}/process`：是否成功转发到 `rag_service`；
   - `POST /api/chat/message`：是否能收到 SSE 流式响应。

---

### 5. 故障排查要点

- **RAG 请求超时或 5xx**：
  - 检查 `RAG_SERVICE_URL` 是否可从互联网访问（可在本地 `curl` 该地址）。
  - 检查 `rag_service` 日志是否有模型加载或数据库错误。

- **上传文档失败**：
  - 检查 Supabase Storage 配置及 Bucket 是否存在。
  - 注意 Vercel 单次请求体有大小限制，大文件需要分块上传。

- **认证相关错误**：
  - 确认前端发送的 JWT 与 backend 的 `JWT_SECRET_KEY`、`JWT_ALGORITHM` 一致。

--- 

更多整体架构与跨服务部署说明，请参考项目根目录的 `DEPLOYMENT.md`。 


