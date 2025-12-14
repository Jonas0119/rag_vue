/**
 * 文档相关类型定义
 */

export interface Document {
  doc_id: string
  user_id: number
  filename: string
  original_filename: string
  file_size: number
  file_type: string
  page_count?: number
  chunk_count: number
  upload_at?: string
  status: string
  error_message?: string
}

export interface DocumentStatus {
  doc_id: string
  status: string
  chunk_count: number
  error_message?: string
}
