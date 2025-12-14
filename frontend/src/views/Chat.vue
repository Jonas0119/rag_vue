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
  background: white;
}

.chat-header {
  padding: 20px;
  border-bottom: 1px solid #e2e8f0;
  background: white;
}

.chat-header h1 {
  margin: 0;
  font-size: 24px;
  color: #2d3748;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.message {
  display: flex;
  max-width: 80%;
}

.message.user {
  align-self: flex-end;
}

.message.assistant {
  align-self: flex-start;
}

.message-content {
  padding: 12px 16px;
  border-radius: 12px;
  background: #f7fafc;
}

.message.user .message-content {
  background: #4299e1;
  color: white;
}

.message-text {
  line-height: 1.6;
  word-wrap: break-word;
}

.cursor {
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

.retrieved-docs,
.thinking-process {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #e2e8f0;
}

details {
  cursor: pointer;
}

summary {
  font-size: 14px;
  color: #667eea;
  margin-bottom: 8px;
}

.doc-item {
  margin: 8px 0;
  padding: 8px;
  background: #edf2f7;
  border-radius: 6px;
}

.doc-header {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  margin-bottom: 4px;
}

.similarity {
  color: #667eea;
}

.doc-content {
  font-size: 13px;
  color: #4a5568;
  max-height: 150px;
  overflow-y: auto;
}

.thinking-step {
  margin: 8px 0;
  padding: 8px;
  background: #f7fafc;
  border-radius: 6px;
  font-size: 13px;
}

.thinking-step pre {
  margin-top: 4px;
  padding: 8px;
  background: #edf2f7;
  border-radius: 4px;
  font-size: 12px;
  overflow-x: auto;
}

.chat-input-container {
  padding: 20px;
  border-top: 1px solid #e2e8f0;
  background: white;
}

.chat-input-form {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.chat-input-form textarea {
  flex: 1;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 14px;
  font-family: inherit;
  resize: none;
}

.chat-input-form textarea:focus {
  outline: none;
  border-color: #4299e1;
}

.chat-input-form textarea:disabled {
  background: #f7fafc;
  cursor: not-allowed;
}

.send-btn {
  padding: 12px 24px;
  background: #4299e1;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.send-btn:hover:not(:disabled) {
  background: #3182ce;
}

.send-btn:disabled {
  background: #cbd5e0;
  cursor: not-allowed;
}
</style>
