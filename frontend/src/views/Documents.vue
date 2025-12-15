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
  padding: var(--spacing-xl);
  max-width: 1200px;
  margin: 0 auto;
  min-height: 100vh;
}

.documents-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-3xl);
  flex-wrap: wrap;
  gap: var(--spacing-md);
}

.documents-header h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.upload-btn {
  min-height: 44px;
  padding: var(--spacing-md) var(--spacing-xl);
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--transition-base);
  white-space: nowrap;
}

.upload-btn:hover {
  background: var(--color-primary-hover);
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

.upload-btn:active {
  transform: translateY(0);
}

.loading {
  text-align: center;
  padding: var(--spacing-3xl);
  color: var(--color-text-secondary);
  font-size: 16px;
}

.empty-state {
  text-align: center;
  padding: 60px var(--spacing-xl);
  color: var(--color-text-muted);
  font-size: 16px;
}

.documents-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.document-item {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: var(--spacing-xl);
  background: var(--color-bg-primary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  transition: all var(--transition-base);
  box-shadow: var(--shadow-sm);
  gap: var(--spacing-lg);
}

.document-item:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--color-primary);
  transform: translateY(-2px);
}

.document-info {
  flex: 1;
  min-width: 0;
}

.document-info h3 {
  margin: 0 0 var(--spacing-md) 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
  word-break: break-word;
}

.document-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-lg);
  font-size: 14px;
  color: var(--color-text-secondary);
  margin-bottom: var(--spacing-sm);
}

.document-meta span {
  white-space: nowrap;
}

.processing-message {
  color: var(--color-primary);
  font-size: 13px;
  margin-top: var(--spacing-sm);
  font-weight: 500;
}

.error-message {
  color: var(--color-danger);
  font-size: 13px;
  margin-top: var(--spacing-sm);
  padding: var(--spacing-sm);
  background: rgba(229, 62, 62, 0.1);
  border-radius: var(--radius-sm);
}

.status-processing {
  color: var(--color-primary);
  font-weight: 600;
}

.status-active {
  color: var(--color-success);
  font-weight: 600;
}

.status-error {
  color: var(--color-danger);
  font-weight: 600;
}

.document-actions {
  display: flex;
  gap: var(--spacing-sm);
  flex-shrink: 0;
}

.delete-btn {
  min-height: 44px;
  padding: var(--spacing-md) var(--spacing-lg);
  background: var(--color-danger);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-base);
  white-space: nowrap;
}

.delete-btn:hover:not(:disabled) {
  background: var(--color-danger-hover);
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.delete-btn:active:not(:disabled) {
  transform: translateY(0);
}

.delete-btn:disabled {
  background: var(--color-border);
  cursor: not-allowed;
  opacity: 0.6;
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
  padding: var(--spacing-lg);
  animation: fadeIn var(--transition-base);
}

.upload-dialog {
  background: var(--color-bg-primary);
  border-radius: var(--radius-xl);
  padding: var(--spacing-3xl);
  width: 100%;
  max-width: 500px;
  box-shadow: var(--shadow-lg);
  animation: slideUp var(--transition-slow);
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.upload-dialog h2 {
  margin: 0 0 var(--spacing-xl) 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.upload-area {
  border: 2px dashed var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--spacing-3xl);
  text-align: center;
  margin-bottom: var(--spacing-xl);
  cursor: pointer;
  transition: all var(--transition-base);
  background: var(--color-bg-secondary);
}

.upload-area:hover {
  border-color: var(--color-primary);
  background: var(--color-bg-hover);
}

.upload-area p {
  color: var(--color-text-secondary);
  margin: var(--spacing-sm) 0;
}

.selected-file {
  color: var(--color-primary);
  font-weight: 600;
  margin: var(--spacing-md) 0;
  display: block;
}

.select-btn {
  min-height: 44px;
  padding: var(--spacing-md) var(--spacing-xl);
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all var(--transition-base);
}

.select-btn:hover {
  background: var(--color-primary-hover);
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-md);
  margin-top: var(--spacing-xl);
}

.cancel-btn,
.upload-confirm-btn {
  min-height: 44px;
  padding: var(--spacing-md) var(--spacing-xl);
  border: none;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-base);
  white-space: nowrap;
}

.cancel-btn {
  background: var(--color-bg-secondary);
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border);
}

.cancel-btn:hover {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
}

.upload-confirm-btn {
  background: var(--color-primary);
  color: white;
}

.upload-confirm-btn:hover:not(:disabled) {
  background: var(--color-primary-hover);
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.upload-confirm-btn:disabled {
  background: var(--color-border);
  cursor: not-allowed;
  opacity: 0.6;
}

/* 移动端响应式 */
@media (max-width: 768px) {
  .documents-container {
    padding: var(--spacing-md);
  }

  .documents-header {
    margin-bottom: var(--spacing-xl);
    padding-left: 72px; /* 为菜单按钮留出空间（16px + 44px + 12px间距），只影响标题区域 */
  }

  .documents-header h1 {
    font-size: 20px;
  }

  .document-item {
    flex-direction: column;
    padding: var(--spacing-lg);
    gap: var(--spacing-md);
  }

  .document-actions {
    width: 100%;
    justify-content: flex-end;
  }

  .delete-btn {
    flex: 1;
    max-width: 120px;
  }

  .document-meta {
    flex-direction: column;
    gap: var(--spacing-sm);
  }

  .upload-dialog {
    padding: var(--spacing-xl);
    margin: var(--spacing-md);
  }

  .upload-area {
    padding: var(--spacing-xl);
  }

  .dialog-actions {
    flex-direction: column-reverse;
  }

  .cancel-btn,
  .upload-confirm-btn {
    width: 100%;
  }
}
</style>
