# Backend 性能优化说明

## 问题描述

当配置了 `RAG_SERVICE_URL`（通过 ngrok 访问 rag_service）后，即使访问不相关的接口（如 `/api/chat/sessions` 和 `/api/documents`）也会变慢。

## 可能的原因

### 1. httpx 模块导入时的初始化开销

**问题**：`httpx` 在模块级别导入时可能会进行一些初始化操作，即使不实际使用。

**解决方案**：已优化为延迟导入（lazy import），只在真正需要调用 rag_service 时才导入 `httpx`。

**修改位置**：
- `backend/api/chat.py`：将 `import httpx` 从模块级别移到函数内部

### 2. ngrok DNS 解析延迟

**问题**：ngrok 的域名解析可能较慢，特别是在首次访问时。

**可能的影响**：
- 即使不调用 rag_service，如果某个地方尝试解析 ngrok URL，DNS 查询可能会很慢
- Python 的某些库可能会在导入时或首次使用时尝试解析 URL

**解决方案**：
- 确保只在真正需要时才解析和使用 `RAG_SERVICE_URL`
- 考虑使用本地 DNS 缓存或配置 hosts 文件

### 3. 环境变量加载延迟

**问题**：配置加载可能会有延迟，特别是在 Vercel 等 Serverless 环境中。

**检查方法**：
- 检查 `backend/utils/config.py` 中的配置加载逻辑
- 确保环境变量加载不会阻塞应用启动

### 4. 其他可能的原因

- **连接池初始化**：httpx 客户端可能会在初始化时创建连接池
- **SSL/TLS 握手**：如果某个地方尝试建立 HTTPS 连接，TLS 握手可能会很慢
- **网络超时设置**：如果超时设置不合理，可能会导致长时间等待

## 已实施的优化

1. ✅ **延迟导入 httpx**：将 `httpx` 的导入从模块级别移到函数内部
2. ✅ **确保只在需要时使用 RAG_SERVICE_URL**：所有使用 `RAG_SERVICE_URL` 的地方都在函数内部，不在模块级别

## 进一步优化建议

### 1. 使用连接池复用

如果频繁调用 rag_service，可以考虑使用全局的 httpx 客户端连接池：

```python
# 在模块级别创建全局客户端（可选）
_rag_service_client = None

def get_rag_service_client():
    global _rag_service_client
    if _rag_service_client is None:
        _rag_service_client = httpx.AsyncClient(timeout=30.0)
    return _rag_service_client
```

### 2. 添加健康检查缓存

如果需要在启动时检查 rag_service 是否可用，可以考虑：
- 使用后台任务进行健康检查
- 缓存健康检查结果
- 避免在每个请求时都进行健康检查

### 3. 优化超时设置

根据实际网络情况调整超时时间：

```python
# 连接超时：5秒
# 读取超时：30秒
timeout = httpx.Timeout(5.0, read=30.0)
```

### 4. 使用异步客户端

确保使用 `httpx.AsyncClient` 而不是同步的 `httpx.Client`，特别是在异步函数中。

## 调试方法

如果问题仍然存在，可以尝试以下调试方法：

1. **添加日志**：在关键位置添加日志，记录每个步骤的耗时
2. **性能分析**：使用 Python 的 `cProfile` 或 `py-spy` 进行性能分析
3. **网络监控**：使用 `tcpdump` 或 `wireshark` 监控网络请求
4. **DNS 测试**：使用 `nslookup` 或 `dig` 测试 ngrok 域名的解析速度

## 测试建议

1. **对比测试**：
   - 不配置 `RAG_SERVICE_URL` 时的响应时间
   - 配置 `RAG_SERVICE_URL` 但访问不相关接口时的响应时间
   - 配置 `RAG_SERVICE_URL` 并访问相关接口时的响应时间

2. **监控指标**：
   - 接口响应时间
   - DNS 解析时间
   - 连接建立时间
   - 请求处理时间

## 注意事项

- 延迟导入 `httpx` 可能会略微增加首次调用的延迟，但可以避免在不需要时进行初始化
- 如果问题仍然存在，可能需要进一步调查网络配置或 ngrok 设置
