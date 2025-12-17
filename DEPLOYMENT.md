## 部署指南（前端 + Backend 网关 + 本地 RAG 服务）

本文档说明如何在新架构下部署整个系统：

- 前端（Vue）部署到 Vercel；
- Backend 作为 Vercel 轻量 API 网关；
- `rag_service` 作为本地/服务器 RAG 服务，通过 ngrok 或反向代理暴露。

---

## 一、部署前准备

### 1. 云服务配置

确保以下云服务已正确配置（与原方案一致）：

- ✅ **Supabase Storage**：文件存储服务
- ✅ **Supabase PostgreSQL**：数据库服务
- ✅ **Pinecone**：向量库服务（如使用云向量库）
- ✅ **LLM API**：MiniMax / Anthropic 等

### 2. RAG 服务配置

RAG 相关逻辑从 `inference_service` 合并到了 `rag_service`：

- Embedding 与 Rerank 模型由 `rag_service` 直接加载（从 ModelScope/HuggingFace 下载）。
- `inference_service/` 目录不再使用，可作为参考或后续删除。

请先完成 `rag_service/DEPLOYMENT.md` 中的步骤，在本地或服务器上启动：

   ```bash
cd rag_service
pip install .
uvicorn rag_service.main:app --host 0.0.0.0 --port 8001
   ngrok http 8001
# 得到 https://your-rag-service.ngrok-free.app
```

记下 ngrok 暴露的 HTTPS 公网地址，用于 backend 的 `RAG_SERVICE_URL`。

---

## 二、部署步骤

### 步骤 1: 准备代码与环境

1. 确保所有代码已提交到 Git 仓库。
2. 确认 `.gitignore` 排除了敏感文件（如 `backend/.env`、`rag_service/.env`）。

### 步骤 2: 部署前端

1. 访问 [Vercel](https://vercel.com/)
2. 使用 GitHub 账号登录
3. 点击 "Add New Project"
4. 选择你的仓库
5. 配置项目：
   - **Root Directory**: `frontend`
   - **Framework Preset**: `Vite`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
6. 添加环境变量：
   - `VITE_API_BASE_URL`: 后端 API 地址（部署后端后获取）

### 步骤 3: 部署 Backend（Vercel 轻量网关）

1. 在 Vercel 中创建新项目
2. 选择同一个仓库
3. 配置项目：
   - **Root Directory**: `backend`
   - **Framework Preset**: `Other`
   - **Build Command**: `pip install .`
   - **Output Directory**: `.`（不需要）
4. 添加所有必要的环境变量（参考下文“环境变量一览”）
5. Vercel 会自动识别 `backend/vercel.json` 配置

### 步骤 4: 配置 Backend 环境变量

在 Vercel 后端项目中，配置（示例）：

```env
# Supabase / 数据库（cloud 模式）
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=your_publishable_key
SUPABASE_SERVICE_KEY=your_service_key
SUPABASE_STORAGE_BUCKET=rag
DATABASE_URL=postgresql://postgres:password@db.xxx.supabase.co:5432/postgres

# 认证
JWT_SECRET_KEY=your_random_secret_key
JWT_EXPIRY_DAYS=30
JWT_ALGORITHM=HS256

# CORS
CORS_ORIGINS=https://your-frontend-domain.vercel.app

# RAG 服务地址（指向 rag_service，经 ngrok 暴露）
RAG_SERVICE_URL=https://your-rag-service.ngrok-free.app
```

Backend 不再需要 `INFERENCE_API_BASE_URL`、`USE_REMOTE_EMBEDDINGS`、`USE_REMOTE_RERANKER` 等变量。

### 步骤 5: 配置 rag_service 环境变量

在运行 `rag_service` 的机器上，按照 `rag_service/DEPLOYMENT.md` 配置：

- LLM 相关：`ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, `LLM_MODEL` 等；
- 模型加载：`EMBEDDING_MODEL`, `RERANKER_MODEL`, `MODEL_DOWNLOAD_SOURCE`；
- 向量库：`VECTOR_DB_MODE`, `PINECONE_*`；
- 存储与数据库：`SUPABASE_*`, `DATABASE_URL` 等。

### 步骤 6: 首次部署

1. 点击 "Deploy" 或等待自动部署
2. 查看构建日志，确认没有错误
3. 如果构建失败，检查：
   - 环境变量是否完整
   - 云服务连接是否正常
   - 数据库是否已初始化

### 步骤 7: 验证部署

部署成功后，测试以下功能：

- [ ] 用户注册/登录
- [ ] 文件上传（验证 Supabase Storage）
- [ ] 创建会话（验证 PostgreSQL）
- [ ] 向量检索（验证 Pinecone）
- [ ] 智能问答功能

## 三、本地环境搭建与开发

> 以下内容整合自原 `ENVIRONMENT_SETUP.md`，帮助你在本地同时搭建 backend、rag_service 和 frontend 的开发环境。

---

### 1. 前置要求

- **Python**: >= 3.10, < 3.14  
- **Node.js**: >= 18.0.0  
- **npm** 或 **yarn**: 最新版本  

示例安装命令：

```bash
# macOS
brew install python@3.11 node

# Ubuntu/Debian
sudo apt-get update
sudo apt-get install python3.11 python3.11-venv nodejs npm
```

---

### 2. Backend 本地环境

#### 2.1 创建虚拟环境并安装依赖

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

# 安装依赖
cd backend
pip install --upgrade pip
pip install .
```

#### 2.2 配置环境变量

```bash
cd backend
cp config_template.txt .env

# 编辑 .env 文件，至少配置：
# - SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_KEY
# - DATABASE_URL（cloud 模式）或 DATABASE_PATH（local 模式）
# - JWT_SECRET_KEY
# - RAG_SERVICE_URL
```

#### 2.3 启动与验证

```bash
cd backend
source venv/bin/activate  # Windows: venv\Scripts\activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 健康检查
curl http://localhost:8000/health
# 浏览器访问: http://localhost:8000/docs
```

---

### 3. RAG Service 本地环境

#### 3.1 创建虚拟环境并安装依赖

```bash
cd /path/to/rag_vue

python3 -m venv rag_service/venv

# 激活虚拟环境
# macOS/Linux:
source rag_service/venv/bin/activate
# Windows:
# rag_service\venv\Scripts\activate

cd rag_service
pip install --upgrade pip
pip install .
```

#### 3.2 配置环境变量

```bash
cd rag_service

cat > .env << EOF
# LLM / API
ANTHROPIC_API_KEY=sk-xxx
ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic
LLM_MODEL=MiniMax-M2

# Embedding & Reranker
EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
EMBEDDING_DEVICE=cpu  # 或 cuda（如果有 GPU）
NORMALIZE_EMBEDDINGS=true
RERANKER_MODEL=BAAI/bge-reranker-base
MODEL_DOWNLOAD_SOURCE=modelscope

# 向量库
VECTOR_DB_MODE=cloud  # cloud: Pinecone, local: Chroma
PINECONE_API_KEY=...
PINECONE_ENVIRONMENT=...
PINECONE_INDEX_NAME=rag-system

# 存储与数据库
STORAGE_MODE=cloud
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=your_publishable_key
SUPABASE_SERVICE_KEY=your_service_key
SUPABASE_STORAGE_BUCKET=rag
DATABASE_URL=postgresql://...

# Checkpoint / LangGraph
USE_CHECKPOINT=true
CHECKPOINT_DB_PATH=data/checkpoints/checkpoints.db
EOF
```

#### 3.3 启动与验证

```bash
cd rag_service
source venv/bin/activate  # Windows: venv\Scripts\activate

# 首次启动会自动下载 Embedding / Reranker 模型
uvicorn rag_service.main:app --host 0.0.0.0 --port 8001

curl http://localhost:8001/health
# 浏览器访问: http://localhost:8001/docs
```

---

### 4. Frontend 本地环境

#### 4.1 安装依赖

```bash
cd /path/to/rag_vue/frontend
npm install
# 或 yarn install
```

#### 4.2 配置环境变量

```bash
cd frontend

cat > .env.local << EOF
VITE_API_BASE_URL=http://localhost:8000
EOF
```

#### 4.3 启动与验证

```bash
cd frontend
npm run dev
# 或 yarn dev

# 浏览器访问: http://localhost:5173
```

---

### 5. 同时运行三个服务

```bash
# 终端1: Backend
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000

# 终端2: RAG Service
cd rag_service
source venv/bin/activate
uvicorn rag_service.main:app --host 0.0.0.0 --port 8001

# 终端3: Frontend
cd frontend
npm run dev
```

可选：使用 `tmux`/`screen` 或 Docker Compose 来管理多个进程（参见原 `ENVIRONMENT_SETUP.md` 中的示例）。

---

### 6. 快速参考

```bash
# Backend 快速启动
cd backend
source venv/bin/activate  # Windows: venv\Scripts\activate
uvicorn main:app --reload --port 8000

# RAG Service 快速启动
cd rag_service
source venv/bin/activate  # Windows: venv\Scripts\activate
uvicorn rag_service.main:app --host 0.0.0.0 --port 8001

# Frontend 快速启动
cd frontend
npm run dev
```

---

## 四、故障排查

### 问题 1: 构建失败

**可能原因：**
- 依赖安装失败
- Python 版本不兼容

**解决方法：**
- 检查构建日志
- 确认 `pyproject.toml` 中的 Python 版本要求
- 在 Vercel 中设置正确的 Python 版本

### 问题 2: 应用启动失败

**可能原因：**
- 环境变量配置不完整
- 云服务连接失败

**解决方法：**
- 检查应用日志
- 验证所有环境变量已正确配置
- 测试云服务连接

### 问题 3: 文件上传失败

**可能原因：**
- Supabase Storage 未配置
- Bucket 不存在
- Vercel 文件大小限制（4.5MB）

**解决方法：**
- 检查 `SUPABASE_STORAGE_BUCKET` 配置
- 在 Supabase Dashboard 中创建 Bucket
- 大文件需要实现分块上传

### 问题 4: 数据库连接失败

**可能原因：**
- `DATABASE_URL` 格式错误
- 数据库未初始化

**解决方法：**
- 检查连接字符串格式
- 运行数据库初始化脚本（`backend/database/init_db_postgres.sql`）

### 问题 5: 向量检索失败

**可能原因：**
- Pinecone Index 不存在
- API Key 无效

**解决方法：**
- 检查 `PINECONE_INDEX_NAME` 配置
- 在 Pinecone Dashboard 中创建 Index（维度 1024）

### 问题 6: CORS 错误

**可能原因：**
- CORS 源配置不正确

**解决方法：**
- 在 `CORS_ORIGINS` 中添加前端域名
- 确保前后端域名都包含在允许列表中

## 📝 注意事项

1. **必须使用云模式**：Vercel Serverless Functions 不支持本地文件系统，必须使用云服务
2. **保护环境变量**：不要将包含真实密钥的文件提交到 Git
3. **监控资源**：注意云服务的配额限制
4. **定期备份**：虽然使用云服务，但建议定期备份重要数据
5. **文件大小限制**：Vercel 有 4.5MB 请求体限制，大文件需要分块上传
6. **冷启动**：Serverless Functions 有冷启动时间，首次请求可能较慢

## 🔗 相关文档

- [Vercel 文档](https://vercel.com/docs)
- [FastAPI 部署指南](https://fastapi.tiangolo.com/deployment/)
- [Supabase 文档](https://supabase.com/docs)
- [Pinecone 文档](https://docs.pinecone.io/)
