/**
 * 用户相关类型定义
 */

export interface User {
  user_id: number
  username: string
  email?: string
  display_name?: string
  created_at?: string
  last_login?: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  username: string
  password: string
  email?: string
  display_name?: string
}

export interface LoginResponse {
  success: boolean
  token?: string
  user?: User
  message?: string
}
