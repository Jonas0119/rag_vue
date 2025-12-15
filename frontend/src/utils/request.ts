/**
 * Axios 请求封装
 */
import axios, { AxiosInstance, AxiosResponse } from 'axios'
import type { ApiResponse } from '@/types/api'

// 创建 axios 实例
const request: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
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
