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
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue'
import { useChatStore } from '@/stores/chat'

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
  
  await chatStore.sendMessage(message)
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

function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

onMounted(async () => {
  // 刷新会话列表
  await chatStore.fetchSessions()
  
  if (chatStore.currentSessionId) {
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
  background: var(--color-bg-primary);
}

.chat-header {
  padding: var(--spacing-xl);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg-primary);
  box-shadow: var(--shadow-sm);
  position: sticky;
  top: 0;
  z-index: 10;
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
  padding: var(--spacing-xl);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xl);
  background: var(--color-bg-secondary);
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
  background: var(--color-border);
  cursor: not-allowed;
  opacity: 0.6;
}

/* 移动端响应式 */
@media (max-width: 768px) {
  .chat-header {
    padding: var(--spacing-md) var(--spacing-lg);
  }

  .chat-header h1 {
    font-size: 20px;
  }

  .chat-messages {
    padding: var(--spacing-lg) var(--spacing-md);
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
