/**
 * 上传任务 Store（管理 TUS 大文件上传进度）
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as tus from 'tus-js-client'
import { documentsApi } from '@/api/documents'
import { useDocumentsStore } from './documents'

export interface UploadTask {
  id: string
  docId: string
  fileName: string
  size: number
  progress: number
  status: 'pending' | 'uploading' | 'success' | 'error'
  error?: string
  uploader?: tus.Upload
}

export const useUploadStore = defineStore('uploads', () => {
  const tasks = ref<UploadTask[]>([])

  function addTask(task: UploadTask) {
    tasks.value.unshift(task)
  }

  function updateTask(id: string, patch: Partial<UploadTask>) {
    const task = tasks.value.find(t => t.id === id)
    if (task) {
      Object.assign(task, patch)
    }
  }

  function completeTask(id: string) {
    updateTask(id, { status: 'success', progress: 100 })
  }

  function failTask(id: string, error: string) {
    updateTask(id, { status: 'error', error })
  }

  async function startUpload(file: File): Promise<string | null> {
    const documentsStore = useDocumentsStore()

    // 第一步：向后端申请 TUS 上传配置（只发送元数据）
    const initConfig = await documentsApi.initTusUpload(file)
    const { endpoint, bucket, object_name, doc_id, max_file_size, supabase_anon_key } = initConfig

    // 如果后端返回了最大允许大小，提前在前端拦截过大的文件，避免 413
    if (max_file_size && file.size > max_file_size) {
      const maxMb = Math.round(max_file_size / (1024 * 1024))
      failTask(doc_id, `文件超过大小限制（最大 ${maxMb} MB）`)
      return null
    }

    // 立刻刷新一次文档列表，让新文档出现在列表中（status=uploading/processing）
    // 避免用户感觉“点了上传没反应”
    await documentsStore.fetchDocuments()

    const task: UploadTask = {
      id: doc_id,
      docId: doc_id,
      fileName: file.name,
      size: file.size,
      progress: 0,
      status: 'pending'
    }
    addTask(task)

    // 第二步：使用 tus-js-client 将文件直传到 Supabase Storage
    const upload = new tus.Upload(file, {
      endpoint,
      metadata: {
        bucketName: bucket,
        objectName: object_name,
        contentType: file.type || 'application/octet-stream'
      },
      headers: {
        ...(supabase_anon_key
          ? {
              Authorization: `Bearer ${supabase_anon_key}`,
              apikey: supabase_anon_key
            }
          : {}),
        'x-upsert': 'false'
      },
      chunkSize: 6 * 1024 * 1024,
      onProgress(bytesSent, bytesTotal) {
        const percent = bytesTotal > 0 ? Math.round((bytesSent / bytesTotal) * 100) : 0
        updateTask(doc_id, { progress: percent, status: 'uploading' })
      },
      async onSuccess() {
        try {
          completeTask(doc_id)
          // 第三步：通知后端上传已完成，触发后台文档处理
          await documentsApi.confirmUpload(doc_id)
          // 刷新文档列表以获取最新状态（processing/active）
          await documentsStore.fetchDocuments()
        } catch (e: any) {
          failTask(doc_id, e?.message || '确认上传失败')
        }
      },
      onError(error) {
        failTask(doc_id, error.message || '上传失败')
      }
    })

    updateTask(doc_id, { uploader: upload, status: 'uploading' })
    upload.start()

    return doc_id
  }

  function cancelUpload(id: string) {
    const task = tasks.value.find(t => t.id === id)
    if (task && task.uploader) {
      task.uploader.abort()
      failTask(id, '已取消上传')
    }
  }

  return {
    tasks,
    addTask,
    updateTask,
    completeTask,
    failTask,
    startUpload,
    cancelUpload
  }
})

