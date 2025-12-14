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
   * 上传文档（异步处理）
   */
  async uploadDocument(file: File): Promise<{ success: boolean; message: string; doc_id?: string; status?: string }> {
    const formData = new FormData()
    formData.append('file', file)

    const response = await request.post<{ success: boolean; message: string; doc_id?: string; status?: string }>(
      '/documents/upload',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data'
        },
        timeout: 60000 // 增加到 60 秒，因为需要保存文件和创建记录
      }
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
