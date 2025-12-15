/**
 * API 响应类型定义
 */

export interface ApiResponse<T = any> {
  success: boolean
  data?: T
  error?: string
  message?: string
  token?: string
}
