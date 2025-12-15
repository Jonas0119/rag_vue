# 部署指南

本文档详细说明如何将 RAG 智能问答系统部署到 Vercel。

## 📋 部署前准备

### 1. 云服务配置

确保以下云服务已正确配置：

- ✅ **Supabase Storage**：文件存储服务（STORAGE_MODE=cloud 时）
- ✅ **Supabase PostgreSQL**：数据库服务（DATABASE_MODE=cloud 时）
- ✅ **Pinecone**：向量库服务（VECTOR_DB_MODE=cloud 时）
- ✅ **LLM API**：MiniMax / OpenAI / Anthropic 等

### 2. 环境变量准备

所有配置通过 Vercel 环境变量管理，参考 `config_template.txt`

### 3. 本地推理服务（ngrok）准备

当前项目 **不在 Vercel 中加载/下载 Embedding 与 Rerank 模型**，而是通过本地 FastAPI 服务 + ngrok 暴露出来的云推理接口：

- 本地目录：`inference_service/`
- 接口：
  - `GET /health`
  - `POST /embed`
  - `POST /rerank`
- 默认端口：`8001`
- 通过 `ngrok http 8001` 暴露为公网 HTTPS 地址（例如：`https://xxx.ngrok-free.dev`）

部署到 Vercel 前，请先在本地完成以下操作：

1. 在项目根目录安装依赖并启动推理服务：

   ```bash
   poetry install
   poetry run uvicorn inference_service.main:app --host 0.0.0.0 --port 8001
   ```

2. 启动 ngrok 暴露本地端口：

   ```bash
   ngrok http 8001
   # 记下返回的 HTTPS 公网 URL，例如：
   # https://nonanesthetized-nolan-riantly.ngrok-free.dev
   ```

3. 在 Vercel 后端项目中，将该 URL 配置到环境变量 `INFERENCE_API_BASE_URL` 中，并确保：

   ```env
   USE_REMOTE_EMBEDDINGS=true
   USE_REMOTE_RERANKER=true   # 若需要远程 rerank
   INFERENCE_API_BASE_URL=https://your-ngrok-url.ngrok-free.dev
   INFERENCE_API_KEY=与你在 inference_service 中配置的 INFERENCE_API_KEY 保持一致
   MODEL_DOWNLOAD_SOURCE=modelscope
   ```

> 注意：Vercel 每次调用后端时，都会通过 `INFERENCE_API_BASE_URL` 访问你本地的推理服务，因此在使用期间需要保持本地 `inference_service` 与 `ngrok` 长期运行。

## 🚀 部署步骤

### 步骤 1: 准备代码

1. 确保所有代码已提交到 Git 仓库
2. 确认 `.gitignore` 排除了敏感文件（`backend/.env`）

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

### 步骤 3: 部署后端

1. 在 Vercel 中创建新项目
2. 选择同一个仓库
3. 配置项目：
   - **Root Directory**: `backend`
   - **Framework Preset**: `Other`
   - **Build Command**: `poetry install`（或 `pip install -r requirements.txt`）
   - **Output Directory**: `.`（不需要）
4. 添加所有必要的环境变量（参考下面的环境变量列表）
5. Vercel 会自动识别 `backend/vercel.json` 配置

### 步骤 4: 配置环境变量

在 Vercel 项目设置中，添加以下环境变量：

#### 基础配置（必须）

```env
ANTHROPIC_API_KEY=sk-xxx
ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic
```

#### 模式配置（必须全部为 cloud）

```env
STORAGE_MODE=cloud
VECTOR_DB_MODE=cloud
DATABASE_MODE=cloud
```

此时：

- **文件存储** 走 Supabase Storage
- **数据库** 走 Supabase PostgreSQL
- **向量库** 走 Pinecone（远程云向量库）
- **Embedding / Rerank** 走本地 `inference_service` + ngrok 暴露的 HTTP 接口（通过上文的 `INFERENCE_API_BASE_URL` 等变量控制）

#### Supabase 配置（STORAGE_MODE=cloud 时必需）

```env
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=your_publishable_key
SUPABASE_SERVICE_KEY=your_service_key
SUPABASE_STORAGE_BUCKET=rag
```

#### PostgreSQL 配置（DATABASE_MODE=cloud 时必需）

```env
DATABASE_URL=postgresql://postgres:password@db.xxx.supabase.co:5432/postgres
```

#### Pinecone 配置（VECTOR_DB_MODE=cloud 时必需）

```env
PINECONE_API_KEY=xxx-xxx-xxx
PINECONE_ENVIRONMENT=us-east-1
PINECONE_INDEX_NAME=rag-system
```

#### 认证配置（必须）

```env
JWT_SECRET_KEY=your_random_secret_key  # 使用: python -c "import secrets; print(secrets.token_urlsafe(32))"
JWT_EXPIRY_DAYS=30
JWT_ALGORITHM=HS256
```

#### CORS 配置（必须）

```env
CORS_ORIGINS=https://your-frontend-domain.vercel.app
```

### 步骤 5: 首次部署

1. 点击 "Deploy" 或等待自动部署
2. 查看构建日志，确认没有错误
3. 如果构建失败，检查：
   - 环境变量是否完整
   - 云服务连接是否正常
   - 数据库是否已初始化

### 步骤 6: 验证部署

部署成功后，测试以下功能：

- [ ] 用户注册/登录
- [ ] 文件上传（验证 Supabase Storage）
- [ ] 创建会话（验证 PostgreSQL）
- [ ] 向量检索（验证 Pinecone）
- [ ] 智能问答功能

## 🔍 故障排查

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
