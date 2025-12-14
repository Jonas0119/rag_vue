/**
 * 文档 Store
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { documentsApi } from '@/api/documents'
import type { Document, DocumentStatus } from '@/types/documents'

export const useDocumentsStore = defineStore('documents', () => {
  const documents = ref<Document[]>([])
  const isLoading = ref(false)

  /**
   * 获取文档列表
   */
  async function fetchDocuments(): Promise<void> {
    isLoading.value = true
    try {
      const docList = await documentsApi.getDocuments()
      documents.value = docList
    } finally {
      isLoading.value = false
    }
  }

  /**
   * 上传文档（异步处理）
   * 返回 doc_id，文档会立即显示在列表中
   */
  async function uploadDocument(file: File): Promise<string | null> {
    isLoading.value = true
    try {
      const result = await documentsApi.uploadDocument(file)
      const docId = result.doc_id || null
      
      if (docId) {
        // 立即刷新文档列表（包含新上传的 processing 状态文档）
        // 这样用户可以看到新上传的文档条目，状态为"处理中"
        await fetchDocuments()
      }
      
      return docId
    } finally {
      isLoading.value = false
    }
  }

  /**
   * 轮询文档状态直到完成或失败
   */
  async function pollDocumentStatus(docId: string, maxAttempts: number = 60, interval: number = 2000): Promise<DocumentStatus> {
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      const status = await documentsApi.getDocumentStatus(docId)
      
      // 如果处理完成（active）或失败（error），停止轮询
      if (status.status === 'active' || status.status === 'error') {
        // 刷新文档列表
        await fetchDocuments()
        return status
      }
      
      // 等待指定时间后继续轮询
      if (attempt < maxAttempts - 1) {
        await new Promise(resolve => setTimeout(resolve, interval))
      }
    }
    
    // 超时，返回当前状态
    const status = await documentsApi.getDocumentStatus(docId)
    await fetchDocuments()
    return status
  }

  /**
   * 删除文档
   */
  async function deleteDocument(docId: string): Promise<void> {
    await documentsApi.deleteDocument(docId)
    documents.value = documents.value.filter(doc => doc.doc_id !== docId)
  }

  return {
    documents,
    isLoading,
    fetchDocuments,
    uploadDocument,
    pollDocumentStatus,
    deleteDocument
  }
})
