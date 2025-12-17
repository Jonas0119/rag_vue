/**
 * 文档 API 客户端
 */
import request from '@/utils/request'
import type { Document, DocumentStatus } from '@/types/documents'

export const documentsApi = {
  /**
   * 获取文档列表
   */
  async getDocuments(): Promise<Document[]> {
    const response = await request.get<Document[]>('/documents')
    return response.data
  },

  /**
   * 初始化 TUS 上传（仅创建文档记录并返回 Supabase 配置）
   */
  async initTusUpload(file: File): Promise<{
    endpoint: string
    bucket: string
    object_name: string
    doc_id: string
    max_file_size: number
    supabase_anon_key?: string
  }> {
    const response = await request.post<{
      endpoint: string
      bucket: string
      object_name: string
      doc_id: string
      max_file_size: number
      supabase_anon_key?: string
    }>('/documents/tus-init', {
      filename: file.name,
      file_size: file.size,
      content_type: file.type || 'application/octet-stream'
    })
    return response.data
  },

  /**
   * 通知后端上传已完成，触发后台文档处理
   */
  async confirmUpload(docId: string): Promise<{ success: boolean; message: string; doc_id?: string; status?: string }> {
    const response = await request.post<{ success: boolean; message: string; doc_id?: string; status?: string }>(
      `/documents/${docId}/confirm-upload`,
      {}
    )
    return response.data
  },

  /**
   * 删除文档
   */
  async deleteDocument(docId: string): Promise<void> {
    await request.delete(`/documents/${docId}`)
  },

  /**
   * 获取文档状态
   */
  async getDocumentStatus(docId: string): Promise<DocumentStatus> {
    const response = await request.get<DocumentStatus>(`/documents/${docId}/status`)
    return response.data
  }
}
