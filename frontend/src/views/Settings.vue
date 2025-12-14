<template>
  <div class="settings-container">
    <div class="settings-header">
      <h1>⚙️ 系统设置</h1>
    </div>

    <div class="settings-content">
      <div class="settings-section">
        <h2>👤 用户信息</h2>
        <div class="info-grid">
          <div class="info-item">
            <label>用户名</label>
            <input :value="authStore.user?.username" disabled />
          </div>
          <div class="info-item">
            <label>显示名称</label>
            <input :value="authStore.user?.display_name || authStore.user?.username" disabled />
          </div>
          <div class="info-item">
            <label>邮箱</label>
            <input :value="authStore.user?.email || '未设置'" disabled />
          </div>
          <div class="info-item">
            <label>注册时间</label>
            <input :value="formatDate(authStore.user?.created_at)" disabled />
          </div>
        </div>
      </div>

      <div class="settings-section">
        <h2>📊 使用统计</h2>
        <div class="stats-grid">
          <div class="stat-item">
            <div class="stat-value">{{ stats.totalSessions }}</div>
            <div class="stat-label">会话数</div>
          </div>
          <div class="stat-item">
            <div class="stat-value">{{ stats.totalMessages }}</div>
            <div class="stat-label">消息数</div>
          </div>
          <div class="stat-item">
            <div class="stat-value">{{ stats.totalDocuments }}</div>
            <div class="stat-label">文档数</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useChatStore } from '@/stores/chat'
import { useDocumentsStore } from '@/stores/documents'

const authStore = useAuthStore()
const chatStore = useChatStore()
const documentsStore = useDocumentsStore()

const stats = computed(() => {
  return {
    totalSessions: chatStore.sessions.length,
    totalMessages: chatStore.sessions.reduce((sum, s) => sum + s.message_count, 0),
    totalDocuments: documentsStore.documents.length
  }
})

function formatDate(dateString?: string): string {
  if (!dateString) return '未知'
  const date = new Date(dateString)
  return date.toLocaleString('zh-CN')
}
</script>

<style scoped>
.settings-container {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.settings-header {
  margin-bottom: 30px;
}

.settings-header h1 {
  margin: 0;
  font-size: 24px;
  color: #2d3748;
}

.settings-content {
  display: flex;
  flex-direction: column;
  gap: 30px;
}

.settings-section {
  background: white;
  padding: 24px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.settings-section h2 {
  margin: 0 0 20px 0;
  font-size: 18px;
  color: #2d3748;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-item label {
  font-size: 14px;
  font-weight: 500;
  color: #4a5568;
}

.info-item input {
  padding: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 14px;
  background: #f7fafc;
  color: #666;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

.stat-item {
  text-align: center;
  padding: 20px;
  background: #f7fafc;
  border-radius: 8px;
}

.stat-value {
  font-size: 32px;
  font-weight: 600;
  color: #4299e1;
  margin-bottom: 8px;
}

.stat-label {
  font-size: 14px;
  color: #666;
}
</style>
