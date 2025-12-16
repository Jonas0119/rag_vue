<template>
  <div class="chat-container">
    <div class="chat-header">
      <h1>💬 智能问答</h1>
    </div>

    <div class="chat-messages" ref="messagesContainer">
      <div
        v-for="(message, index) in chatStore.messages"
        :key="index"
        :class="['message', message.role]"
      >
        <div class="message-content">
          <div
            class="message-actions"
            v-if="message.message_id !== undefined"
          >
            <button
              class="delete-btn"
              type="button"
              @click="handleDeleteMessage(message)"
            >
              删除
            </button>
          </div>
          <div class="message-text" v-html="formatMessage(message.content)"></div>
          
          <div v-if="message.retrieved_docs && message.retrieved_docs.length > 0" class="retrieved-docs">
            <details>
              <summary>📄 检索到的文档片段 ({{ message.retrieved_docs.length }})</summary>
              <div v-for="(doc, idx) in message.retrieved_docs" :key="idx" class="doc-item">
                <div class="doc-header">
                  <span>片段 {{ idx + 1 }}</span>
                  <span v-if="doc.similarity" class="similarity">
                    相似度: {{ (doc.similarity * 100).toFixed(0) }}%
                  </span>
                </div>
                <div class="doc-content">{{ doc.content }}</div>
              </div>
            </details>
          </div>

          <div v-if="message.thinking_process && message.thinking_process.length > 0" class="thinking-process">
            <details>
              <summary>💭 AI 思考过程</summary>
              <div v-for="step in message.thinking_process" :key="step.step" class="thinking-step">
                <strong>步骤 {{ step.step }}: {{ step.action }}</strong>
                <p>{{ step.description }}</p>
                <pre v-if="step.details">{{ step.details }}</pre>
              </div>
            </details>
          </div>
        </div>
      </div>

      <div v-if="chatStore.isStreaming" class="message assistant">
        <div class="message-content">
          <!-- 调试信息 -->
          <!-- <div style="font-size: 12px; color: #999; margin-bottom: 10px;">
            DEBUG: isStreaming={{ chatStore.isStreaming }}, activeNodes.length={{ chatStore.activeNodes.length }}
          </div> -->
          
          <!-- 节点状态展示 -->
          <div v-if="chatStore.activeNodes.length > 0" class="node-status">
            <div 
              v-for="(node, index) in chatStore.activeNodes" 
              :key="node.node || index" 
              class="node-card"
              :class="{
                'node-running': node.status === 'running',
                'node-completed': node.status === 'completed',
                'node-error': node.status === 'error'
              }"
            >
              <div class="node-header">
                <span class="node-step">{{ index + 1 }}</span>
                <span class="node-name">{{ node.node_name }}</span>
                <span 
                  class="node-status-badge" 
                  :class="{
                    'status-running': node.status === 'running',
                    'status-completed': node.status === 'completed',
                    'status-error': node.status === 'error'
                  }"
                >
                  {{ getStatusText(node.status) }}
                </span>
              </div>
              <div class="node-description">{{ node.description }}</div>
              <div v-if="node.progress !== undefined && node.status === 'running'" class="node-progress">
                <div class="progress-bar" :style="{ width: node.progress + '%' }"></div>
              </div>
              <div v-if="node.result && node.status === 'completed'" class="node-result">
                <span class="result-label">结果:</span>
                <span class="result-value">{{ formatNodeResult(node.result) }}</span>
              </div>
            </div>
          </div>
          
          <!-- 流式文本内容 -->
          <div class="message-text">
            {{ chatStore.currentMessage || '🤔 大模型正在思考中...' }}
            <span class="cursor">|</span>
          </div>
        </div>
      </div>
    </div>

    <div class="chat-input-container">
      <form @submit.prevent="handleSendMessage" class="chat-input-form">
        <textarea
          v-model="inputMessage"
          placeholder="输入您的问题..."
          rows="3"
          :disabled="chatStore.isStreaming"
          @keydown.enter.exact.prevent="handleSendMessage"
          @keydown.shift.enter.exact="inputMessage += '\n'"
        ></textarea>
        <button 
          type="submit" 
          class="send-btn"
          :disabled="!inputMessage.trim() || chatStore.isStreaming"
        >
          {{ chatStore.isStreaming ? '发送中...' : '发送' }}
        </button>
      </form>

      <!-- 超时重试提示 -->
      <div 
        v-if="chatStore.hasTimeout && !chatStore.isStreaming" 
        class="retry-hint"
      >
        <span>本次回答超时，可能是模型或网络较慢。</span>
        <button class="retry-btn" @click="handleRetry" type="button">
          重试刚才的问题
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue'
import { useChatStore } from '@/stores/chat'
import type { Message } from '@/types/chat'

const chatStore = useChatStore()
const inputMessage = ref('')
const messagesContainer = ref<HTMLElement | null>(null)

function formatMessage(content: string): string {
  // 简单的 Markdown 转 HTML（可以后续使用 marked 库）
  return content
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
}

async function handleSendMessage() {
  if (!inputMessage.value.trim() || chatStore.isStreaming) return

  const message = inputMessage.value.trim()
  inputMessage.value = ''
  
  console.log('[Chat.vue] 发送消息:', message)
  console.log('[Chat.vue] 发送前 isStreaming:', chatStore.isStreaming)
  console.log('[Chat.vue] 发送前 activeNodes:', chatStore.activeNodes)
  
  await chatStore.sendMessage(message)
}

async function handleRetry() {
  await chatStore.retryLastQuestion()
}

// 自动滚动到底部
watch(() => chatStore.messages.length, () => {
  nextTick(() => {
    scrollToBottom()
  })
})

watch(() => chatStore.currentMessage, () => {
  nextTick(() => {
    scrollToBottom()
  })
})

async function handleDeleteMessage(message: Message) {
  try {
    await chatStore.deleteMessage(message.message_id!)
  } catch (error: any) {
    console.error('删除消息失败:', error)
    alert(error.message || '删除消息失败，请稍后重试')
  }
}

function getStatusText(status: string): string {
  const statusMap: Record<string, string> = {
    'pending': '等待中',
    'running': '执行中',
    'completed': '已完成',
    'error': '错误'
  }
  return statusMap[status] || status
}

function formatNodeResult(result: any): string {
  if (!result) return ''
  if (typeof result === 'string') return result
  if (result.action) {
    if (result.doc_count !== undefined) {
      return `检索到 ${result.doc_count} 个文档`
    }
    if (result.answer_length !== undefined) {
      return `生成了 ${result.answer_length} 字符的答案`
    }
    return result.action
  }
  return JSON.stringify(result)
}

function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

onMounted(async () => {
  // 初始加载：拉取会话并自动选中最近一条；若无历史则清空界面
  if (!chatStore.sessions.length) {
    await chatStore.loadLatestSession()
  } else if (chatStore.currentSessionId) {
    await chatStore.fetchSessionMessages(chatStore.currentSessionId)
  }
})

// 监听消息变化，实时更新会话的消息计数
// 注意：这里主要用于 UI 同步，最终计数应该从后端获取
watch(() => chatStore.messages.length, () => {
  if (chatStore.currentSessionId && !chatStore.isStreaming) {
    // 只在非流式状态下更新，避免在发送消息过程中频繁更新
    chatStore.updateSessionMessageCountFromMessages(chatStore.currentSessionId)
  }
})
</script>

<style scoped>
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: 1200px;
  margin: 0 auto;
  background: var(--color-bg-secondary);
  padding: var(--spacing-xl);
}

.chat-header {
  margin-bottom: var(--spacing-3xl);
}

.chat-header h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xl);
  margin-bottom: var(--spacing-xl);
}

.message {
  display: flex;
  max-width: 80%;
  animation: messageSlideIn var(--transition-base);
}

@keyframes messageSlideIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message.user {
  align-self: flex-end;
}

.message.assistant {
  align-self: flex-start;
}

.message-content {
  padding: var(--spacing-md) var(--spacing-lg);
  border-radius: var(--radius-xl);
  background: var(--color-bg-primary);
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-sm);
  transition: all var(--transition-base);
}

.message-content:hover {
  box-shadow: var(--shadow-md);
}

.message-actions {
  display: flex;
  justify-content: flex-end;
  margin-bottom: var(--spacing-xs);
}

.delete-btn {
  background: transparent;
  border: 1px solid var(--color-border);
  color: var(--color-text-secondary);
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  cursor: pointer;
  transition: all var(--transition-base);
}

.delete-btn:hover {
  color: var(--color-danger, #e53e3e);
  border-color: var(--color-danger, #e53e3e);
}

.message.user .message-content {
  background: var(--color-primary);
  color: white;
  border-color: var(--color-primary);
}

.message.user .message-content:hover {
  background: var(--color-primary-hover);
  border-color: var(--color-primary-hover);
}

.message-text {
  line-height: 1.6;
  word-wrap: break-word;
  color: var(--color-text-primary);
}

.message.user .message-text {
  color: white;
}

.cursor {
  animation: blink 1s infinite;
  display: inline-block;
  margin-left: 2px;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

.retrieved-docs,
.thinking-process {
  margin-top: var(--spacing-md);
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--color-border);
}

details {
  cursor: pointer;
  transition: all var(--transition-base);
}

details:hover {
  opacity: 0.9;
}

summary {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-primary);
  margin-bottom: var(--spacing-sm);
  user-select: none;
}

summary:hover {
  color: var(--color-primary-hover);
}

.doc-item {
  margin: var(--spacing-sm) 0;
  padding: var(--spacing-md);
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  transition: all var(--transition-base);
}

.doc-item:hover {
  background: var(--color-bg-hover);
  border-color: var(--color-primary);
  box-shadow: var(--shadow-sm);
}

.doc-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  font-weight: 500;
  margin-bottom: var(--spacing-xs);
  color: var(--color-text-secondary);
}

.similarity {
  color: var(--color-primary);
  font-weight: 600;
}

.doc-content {
  font-size: 13px;
  color: var(--color-text-primary);
  max-height: 150px;
  overflow-y: auto;
  line-height: 1.5;
}

.thinking-step {
  margin: var(--spacing-sm) 0;
  padding: var(--spacing-md);
  background: var(--color-bg-primary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: 13px;
  transition: all var(--transition-base);
}

.thinking-step:hover {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-sm);
}

.thinking-step strong {
  color: var(--color-text-primary);
  display: block;
  margin-bottom: var(--spacing-xs);
}

.thinking-step p {
  color: var(--color-text-secondary);
  margin: var(--spacing-xs) 0;
  line-height: 1.5;
}

.thinking-step pre {
  margin-top: var(--spacing-sm);
  padding: var(--spacing-md);
  background: var(--color-bg-secondary);
  border-radius: var(--radius-sm);
  font-size: 12px;
  overflow-x: auto;
  border: 1px solid var(--color-border);
}

/* 节点状态样式 */
.node-status {
  margin-bottom: var(--spacing-md);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.node-card {
  padding: var(--spacing-md);
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  transition: all var(--transition-base);
  animation: nodeSlideIn 0.3s ease-out;
}

@keyframes nodeSlideIn {
  from {
    opacity: 0;
    transform: translateX(-10px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.node-card.node-running {
  border-left: 3px solid var(--color-primary);
  background: rgba(66, 153, 225, 0.05);
}

.node-card.node-completed {
  border-left: 3px solid #48bb78;
  background: rgba(72, 187, 120, 0.05);
}

.node-card.node-error {
  border-left: 3px solid #e53e3e;
  background: rgba(229, 62, 62, 0.05);
}

.node-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-xs);
}

.node-step {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--color-primary);
  color: white;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.node-name {
  font-weight: 600;
  color: var(--color-text-primary);
  font-size: 14px;
  flex: 1;
}

.node-status-badge {
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: 500;
  text-transform: uppercase;
}

.node-status-badge.status-running {
  background: rgba(66, 153, 225, 0.2);
  color: var(--color-primary);
}

.node-status-badge.status-completed {
  background: rgba(72, 187, 120, 0.2);
  color: #48bb78;
}

.node-status-badge.status-error {
  background: rgba(229, 62, 62, 0.2);
  color: #e53e3e;
}

.node-description {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-bottom: var(--spacing-xs);
  line-height: 1.5;
}

.node-progress {
  margin-top: var(--spacing-xs);
  height: 4px;
  background: var(--color-bg-primary);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: var(--color-primary);
  border-radius: var(--radius-sm);
  transition: width 0.3s ease;
  animation: progressPulse 1.5s ease-in-out infinite;
}

@keyframes progressPulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

.node-result {
  margin-top: var(--spacing-xs);
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--color-bg-primary);
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--color-text-secondary);
}

.result-label {
  font-weight: 500;
  color: var(--color-text-primary);
  margin-right: var(--spacing-xs);
}

.result-value {
  color: var(--color-text-secondary);
}

.chat-input-container {
  padding: var(--spacing-xl);
  border-top: 1px solid var(--color-border);
  background: var(--color-bg-primary);
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.05);
  position: sticky;
  bottom: 0;
  z-index: 10;
}

.chat-input-form {
  display: flex;
  gap: var(--spacing-md);
  align-items: flex-end;
  max-width: 100%;
}

.chat-input-form textarea {
  flex: 1;
  min-height: 44px;
  padding: var(--spacing-md);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  font-size: 14px;
  font-family: inherit;
  resize: none;
  background: var(--color-bg-primary);
  color: var(--color-text-primary);
  transition: all var(--transition-base);
}

.chat-input-form textarea:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(66, 153, 225, 0.1);
}

.chat-input-form textarea:disabled {
  background: var(--color-bg-secondary);
  cursor: not-allowed;
  opacity: 0.6;
}

.retry-hint {
  margin-top: var(--spacing-md);
  font-size: 13px;
  color: var(--color-text-secondary);
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.retry-btn {
  padding: 4px 10px;
  font-size: 12px;
  border-radius: var(--radius-md);
  border: none;
  background: var(--color-primary);
  color: #fff;
  cursor: pointer;
  transition: background var(--transition-base), transform var(--transition-base);
}

.retry-btn:hover {
  background: var(--color-primary-hover);
  transform: translateY(-1px);
}

.send-btn {
  min-width: 80px;
  min-height: 44px;
  padding: var(--spacing-md) var(--spacing-2xl);
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius-lg);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--transition-base);
  white-space: nowrap;
}

.send-btn:hover:not(:disabled) {
  background: var(--color-primary-hover);
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

.send-btn:active:not(:disabled) {
  transform: translateY(0);
}

.send-btn:disabled {
  background: #cbd5e0;
  color: #718096;
  cursor: not-allowed;
  opacity: 1;
}

/* 移动端响应式 */
@media (max-width: 768px) {
  .chat-container {
    padding: var(--spacing-md);
  }

  .chat-header {
    margin-bottom: var(--spacing-xl);
    padding-left: 72px; /* 为菜单按钮留出空间（16px + 44px + 12px间距） */
  }

  .chat-header h1 {
    font-size: 20px;
  }

  .chat-messages {
    margin-bottom: var(--spacing-md);
    gap: var(--spacing-lg);
  }

  .message {
    max-width: 90%;
  }

  .message-content {
    padding: var(--spacing-md);
    border-radius: var(--radius-lg);
  }

  .chat-input-container {
    padding: var(--spacing-md);
  }

  .chat-input-form {
    gap: var(--spacing-sm);
  }

  .chat-input-form textarea {
    font-size: 16px; /* 防止iOS自动缩放 */
    min-height: 44px;
  }

  .send-btn {
    min-width: 70px;
    padding: var(--spacing-md) var(--spacing-lg);
    font-size: 14px;
  }

  .doc-content {
    max-height: 120px;
  }
}
</style>
