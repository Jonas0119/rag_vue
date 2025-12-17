/**
 * 文档 Store
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { documentsApi } from '@/api/documents'
import type { Document, DocumentStatus } from '@/types/documents'
import { useUploadStore } from './uploads'

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
      // 双重保障：过滤掉 deleted 状态的文档（后端已过滤，这里作为额外保障）
      documents.value = docList.filter(doc => doc.status !== 'deleted')
    } finally {
      isLoading.value = false
    }
  }

  /**
   * 启动文档上传（使用 TUS 分片），不阻塞页面。
   * 返回 doc_id，文档会立即显示在列表中，由上传 Store 负责具体上传与进度。
   */
  async function uploadDocument(file: File): Promise<string | null> {
    const uploadStore = useUploadStore()
    isLoading.value = true
    try {
      // 由上传 Store 负责完整的 TUS 上传流程
      const taskDocId = await uploadStore.startUpload(file)
      return taskDocId
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
    // 从列表中移除（乐观更新）
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
