<template>
  <div class="documents-container">
    <div class="documents-header">
      <h1>📁 知识库管理</h1>
      <button @click="showUploadDialog = true" class="upload-btn">+ 上传文档</button>
    </div>

    <div v-if="documentsStore.isLoading" class="loading">
      加载中...
    </div>

    <div v-else-if="documentsStore.documents.length === 0" class="empty-state">
      <p>暂无文档，请上传文档开始使用</p>
    </div>

    <div v-else class="documents-list">
      <div
        v-for="doc in documentsStore.documents"
        :key="doc.doc_id"
        class="document-item"
      >
        <div class="document-info">
          <h3>{{ doc.original_filename }}</h3>
          <div class="document-meta">
            <span>大小: {{ formatFileSize(doc.file_size) }}</span>
            <span>类型: {{ doc.file_type }}</span>
            <span>块数: {{ doc.chunk_count }}</span>
            <span :class="{
              'status-processing': doc.status === 'processing',
              'status-active': doc.status === 'active',
              'status-error': doc.status === 'error'
            }">
              状态: {{ getStatusText(doc.status) }}
            </span>
          </div>
          <div v-if="doc.status === 'processing'" class="processing-message">
            ⏳ 正在处理中，请稍候...
          </div>
          <div v-if="doc.error_message" class="error-message">
            错误: {{ doc.error_message }}
          </div>
        </div>
        <div class="document-actions">
          <button 
            @click="handleDelete(doc.doc_id)" 
            class="delete-btn"
            :disabled="documentsStore.isLoading"
          >
            删除
          </button>
        </div>
      </div>
    </div>

    <!-- 上传对话框 -->
    <div v-if="showUploadDialog" class="upload-dialog-overlay" @click="showUploadDialog = false">
      <div class="upload-dialog" @click.stop>
        <h2>上传文档</h2>
        <div class="upload-area" 
             @drop="handleDrop"
             @dragover.prevent
             @dragenter.prevent>
          <input
            ref="fileInput"
            type="file"
            accept=".pdf,.txt,.md,.docx"
            @change="handleFileSelect"
            style="display: none"
          />
          <p v-if="!selectedFile">拖拽文件到此处或点击选择</p>
          <p v-else class="selected-file">{{ selectedFile.name }}</p>
          <button @click="fileInput?.click()" class="select-btn">选择文件</button>
        </div>
        <div class="dialog-actions">
          <button @click="showUploadDialog = false" class="cancel-btn">取消</button>
          <button 
            @click="handleUpload" 
            class="upload-confirm-btn"
            :disabled="!selectedFile || uploading"
          >
            {{ uploading ? '上传中...' : '上传' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useDocumentsStore } from '@/stores/documents'

const documentsStore = useDocumentsStore()
const showUploadDialog = ref(false)
const selectedFile = ref<File | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const uploading = ref(false)

onMounted(async () => {
  await documentsStore.fetchDocuments()
})

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

function getStatusText(status: string): string {
  const statusMap: Record<string, string> = {
    'processing': '处理中',
    'active': '已完成',
    'error': '处理失败'
  }
  return statusMap[status] || status
}

function handleFileSelect(event: Event) {
  const target = event.target as HTMLInputElement
  if (target.files && target.files[0]) {
    selectedFile.value = target.files[0]
  }
}

function handleDrop(event: DragEvent) {
  event.preventDefault()
  if (event.dataTransfer?.files && event.dataTransfer.files[0]) {
    selectedFile.value = event.dataTransfer.files[0]
  }
}

async function handleUpload() {
  if (!selectedFile.value) return

  uploading.value = true
  try {
    // 上传文档（立即返回，后台处理）
    // uploadDocument 内部会立即刷新列表，显示新上传的文档
    const docId = await documentsStore.uploadDocument(selectedFile.value)
    
    if (docId) {
      // 关闭上传对话框
      showUploadDialog.value = false
      selectedFile.value = null
      
      // 可选：自动轮询状态直到完成
      // 在后台静默轮询，不阻塞用户操作
      if (docId) {
        documentsStore.pollDocumentStatus(docId).catch(err => {
          console.error('状态轮询失败:', err)
        })
      }
    } else {
      alert('上传失败：未返回文档ID')
    }
  } catch (error: any) {
    alert(error.message || '上传失败')
  } finally {
    uploading.value = false
  }
}

async function handleDelete(docId: string) {
  if (!confirm('确定要删除这个文档吗？')) return

  try {
    await documentsStore.deleteDocument(docId)
  } catch (error: any) {
    alert(error.message || '删除失败')
  }
}
</script>

<style scoped>
.documents-container {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.documents-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
}

.documents-header h1 {
  margin: 0;
  font-size: 24px;
  color: #2d3748;
}

.upload-btn {
  padding: 10px 20px;
  background: #4299e1;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.upload-btn:hover {
  background: #3182ce;
}

.loading {
  text-align: center;
  padding: 40px;
  color: #666;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #999;
}

.documents-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.document-item {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 20px;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  transition: box-shadow 0.2s;
}

.document-item:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.document-info {
  flex: 1;
}

.document-info h3 {
  margin: 0 0 12px 0;
  font-size: 16px;
  color: #2d3748;
}

.document-meta {
  display: flex;
  gap: 16px;
  font-size: 14px;
  color: #666;
  margin-bottom: 8px;
}

.processing-message {
  color: #4299e1;
  font-size: 13px;
  margin-top: 8px;
  font-weight: 500;
}

.error-message {
  color: #e53e3e;
  font-size: 13px;
  margin-top: 8px;
}

.status-processing {
  color: #4299e1;
  font-weight: 500;
}

.status-active {
  color: #48bb78;
  font-weight: 500;
}

.status-error {
  color: #e53e3e;
  font-weight: 500;
}

.document-actions {
  display: flex;
  gap: 8px;
}

.delete-btn {
  padding: 8px 16px;
  background: #e53e3e;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
}

.delete-btn:hover:not(:disabled) {
  background: #c53030;
}

.delete-btn:disabled {
  background: #cbd5e0;
  cursor: not-allowed;
}

.upload-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.upload-dialog {
  background: white;
  border-radius: 12px;
  padding: 30px;
  width: 90%;
  max-width: 500px;
}

.upload-dialog h2 {
  margin: 0 0 20px 0;
  font-size: 20px;
}

.upload-area {
  border: 2px dashed #cbd5e0;
  border-radius: 8px;
  padding: 40px;
  text-align: center;
  margin-bottom: 20px;
  cursor: pointer;
  transition: border-color 0.2s;
}

.upload-area:hover {
  border-color: #4299e1;
}

.selected-file {
  color: #4299e1;
  font-weight: 600;
  margin: 10px 0;
}

.select-btn {
  padding: 10px 20px;
  background: #4299e1;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}

.select-btn:hover {
  background: #3182ce;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.cancel-btn,
.upload-confirm-btn {
  padding: 10px 20px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
}

.cancel-btn {
  background: #e2e8f0;
  color: #4a5568;
}

.cancel-btn:hover {
  background: #cbd5e0;
}

.upload-confirm-btn {
  background: #4299e1;
  color: white;
}

.upload-confirm-btn:hover:not(:disabled) {
  background: #3182ce;
}

.upload-confirm-btn:disabled {
  background: #cbd5e0;
  cursor: not-allowed;
}
</style>
