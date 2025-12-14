/**
 * 认证 API 客户端
 */
import request from '@/utils/request'
import type { LoginRequest, RegisterRequest, LoginResponse, User } from '@/types/user'

export const authApi = {
  /**
   * 用户登录
   */
  async login(credentials: LoginRequest): Promise<LoginResponse> {
    const response = await request.post<LoginResponse>('/auth/login', credentials)
    return response.data
  },

  /**
   * 用户注册
   */
  async register(data: RegisterRequest): Promise<LoginResponse> {
    const response = await request.post<LoginResponse>('/auth/register', data)
    return response.data
  },

  /**
   * 用户登出
   */
  async logout(): Promise<void> {
    await request.post('/auth/logout')
    localStorage.removeItem('token')
  },

  /**
   * 获取当前用户信息
   */
  async getCurrentUser(): Promise<User> {
    const response = await request.get<User>('/auth/me')
    return response.data
  }
}
