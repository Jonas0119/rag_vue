/**
 * Axios 请求封装
 */
import axios, { AxiosInstance, AxiosResponse } from 'axios'
import type { ApiResponse } from '@/types/api'

// 获取 API base URL
// Backend 的 API 前缀是 /api，所以需要确保 baseURL 包含 /api
// 如果设置了 VITE_API_BASE_URL，使用它（应该是完整的 URL，如 https://api.example.com）
// 否则使用相对路径 /api（适用于同一 Vercel 项目或通过 proxy 转发）
const getBaseURL = (): string => {
  const envUrl = import.meta.env.VITE_API_BASE_URL
  if (!envUrl) {
    return '/api'
  }
  
  // 如果已经是完整 URL（以 http:// 或 https:// 开头）
  if (envUrl.startsWith('http://') || envUrl.startsWith('https://')) {
    // 如果 URL 已经以 /api 结尾，直接使用
    if (envUrl.endsWith('/api') || envUrl.endsWith('/api/')) {
      return envUrl.replace(/\/$/, '') // 移除末尾的斜杠
    }
    // 否则添加 /api
    return `${envUrl.replace(/\/$/, '')}/api`
  }
  
  // 如果以 / 开头，是相对路径，直接使用（应该已经是 /api）
  if (envUrl.startsWith('/')) {
    return envUrl
  }
  
  // 否则，假设是域名但没有协议，添加 https:// 和 /api
  const cleanUrl = envUrl.replace(/\/$/, '')
  // 检查是否已经包含 /api
  if (cleanUrl.endsWith('/api')) {
    return `https://${cleanUrl}`
  }
  return `https://${cleanUrl}/api`
}

// 创建 axios 实例
const request: AxiosInstance = axios.create({
  baseURL: getBaseURL(),
  timeout: 60000, // 增加到 60 秒，支持文件上传
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
request.interceptors.request.use(
  (config) => {
    // 从 localStorage 获取 token
    const token = localStorage.getItem('token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    
    // 如果是 FormData，移除默认的 Content-Type，让浏览器自动设置（包括 boundary）
    // 这对于文件上传非常重要，手动设置会破坏 multipart/form-data 的格式
    if (config.data instanceof FormData) {
      delete config.headers['Content-Type']
    }
    
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
request.interceptors.response.use(
  (response: AxiosResponse<ApiResponse>) => {
    const res = response.data
    
    // 如果响应中有 token，保存到 localStorage
    if (res.token) {
      localStorage.setItem('token', res.token)
    }
    
    return response
  },
  (error) => {
    // 处理错误响应
    if (error.response) {
      const { status, data } = error.response
      
      // 401 未授权，清除 token 并跳转到登录页
      if (status === 401) {
        localStorage.removeItem('token')
        window.location.href = '/login'
      }
      
      // 返回错误信息
      return Promise.reject(data || error)
    }
    
    return Promise.reject(error)
  }
)

export default request
