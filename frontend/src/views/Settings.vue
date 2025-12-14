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
  padding: var(--spacing-xl);
  max-width: 1200px;
  margin: 0 auto;
  min-height: 100vh;
}

.settings-header {
  margin-bottom: var(--spacing-3xl);
}

.settings-header h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.settings-content {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-3xl);
}

.settings-section {
  background: var(--color-bg-primary);
  padding: var(--spacing-2xl);
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-sm);
  transition: all var(--transition-base);
}

.settings-section:hover {
  box-shadow: var(--shadow-md);
}

.settings-section h2 {
  margin: 0 0 var(--spacing-xl) 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--spacing-xl);
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.info-item label {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-secondary);
}

.info-item input {
  padding: var(--spacing-md);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: 14px;
  background: var(--color-bg-secondary);
  color: var(--color-text-primary);
  transition: all var(--transition-base);
}

.info-item input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(66, 153, 225, 0.1);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--spacing-xl);
}

.stat-item {
  text-align: center;
  padding: var(--spacing-xl);
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  transition: all var(--transition-base);
}

.stat-item:hover {
  background: var(--color-bg-hover);
  border-color: var(--color-primary);
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.stat-value {
  font-size: 32px;
  font-weight: 600;
  color: var(--color-primary);
  margin-bottom: var(--spacing-sm);
  line-height: 1.2;
}

.stat-label {
  font-size: 14px;
  color: var(--color-text-secondary);
  font-weight: 500;
}

/* 移动端响应式 */
@media (max-width: 768px) {
  .settings-container {
    padding: var(--spacing-md);
  }

  .settings-header {
    margin-bottom: var(--spacing-xl);
  }

  .settings-header h1 {
    font-size: 20px;
  }

  .settings-content {
    gap: var(--spacing-xl);
  }

  .settings-section {
    padding: var(--spacing-lg);
  }

  .info-grid {
    grid-template-columns: 1fr;
    gap: var(--spacing-lg);
  }

  .stats-grid {
    grid-template-columns: 1fr;
    gap: var(--spacing-lg);
  }

  .stat-item {
    padding: var(--spacing-lg);
  }

  .stat-value {
    font-size: 28px;
  }
}

/* 平板端 */
@media (min-width: 769px) and (max-width: 1024px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
