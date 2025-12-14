/**
 * 聊天 Store
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { chatApi } from '@/api/chat'
import type { Message, Session, ChatMessageRequest, SSEChunk } from '@/types/chat'

export const useChatStore = defineStore('chat', () => {
  const currentSessionId = ref<string | null>(null)
  const sessions = ref<Session[]>([])
  const messages = ref<Message[]>([])
  const currentMessage = ref<string>('')
  const isStreaming = ref(false)
  const streamingController = ref<{ close: () => void } | null>(null)

  /**
   * 当前会话
   */
  const currentSession = computed(() => {
    if (!currentSessionId.value) return null
    return sessions.value.find(s => s.session_id === currentSessionId.value) || null
  })

  /**
   * 获取会话列表
   */
  async function fetchSessions(): Promise<void> {
    const sessionList = await chatApi.getSessions()
    sessions.value = sessionList
  }

  /**
   * 创建新会话
   */
  async function createSession(title?: string): Promise<Session> {
    const session = await chatApi.createSession(title)
    sessions.value.unshift(session)
    currentSessionId.value = session.session_id
    return session
  }

  /**
   * 选择会话
   */
  async function selectSession(sessionId: string): Promise<void> {
    currentSessionId.value = sessionId
    await fetchSessionMessages(sessionId)
    // 选择会话后，基于实际消息数量更新会话的消息计数
    updateSessionMessageCountFromMessages(sessionId)
  }

  /**
   * 根据实际消息数量更新会话的消息计数
   * 注意：这个方法主要用于选择会话时的同步，消息发送完成后应该从后端重新获取
   */
  function updateSessionMessageCountFromMessages(sessionId: string): void {
    const session = sessions.value.find(s => s.session_id === sessionId)
    if (session) {
      // 基于当前会话的实际消息数量更新（只统计已保存的消息，排除空内容的占位符）
      const actualCount = messages.value.filter(
        m => m.session_id === sessionId && m.content && m.content.trim()
      ).length
      // 只有当实际消息数量大于0时才更新，避免覆盖后端返回的正确计数
      if (actualCount > 0) {
        session.message_count = actualCount
      }
    }
  }

  /**
   * 获取会话消息
   */
  async function fetchSessionMessages(sessionId: string): Promise<void> {
    const messageList = await chatApi.getSessionMessages(sessionId)
    messages.value = messageList
    // 获取消息后，更新会话的消息计数
    updateSessionMessageCountFromMessages(sessionId)
  }

  /**
   * 发送消息
   */
  async function sendMessage(message: string): Promise<void> {
    if (!message.trim()) return

    // 添加用户消息到列表
    const userMessage: Message = {
      session_id: currentSessionId.value || '',
      role: 'user',
      content: message,
      created_at: new Date().toISOString()
    }
    messages.value.push(userMessage)

    // 如果没有会话，创建新会话
    if (!currentSessionId.value) {
      const session = await createSession(message.substring(0, 20))
      currentSessionId.value = session.session_id
      userMessage.session_id = session.session_id
    }

    // 创建 AI 消息占位符
    const aiMessage: Message = {
      session_id: currentSessionId.value,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString()
    }
    messages.value.push(aiMessage)

    // 开始流式接收
    isStreaming.value = true
    currentMessage.value = ''

    const request: ChatMessageRequest = {
      message,
      session_id: currentSessionId.value
    }

    streamingController.value = chatApi.sendMessage(
      request,
      (chunk: SSEChunk) => {
        if (chunk.type === 'chunk' && chunk.content) {
          // 追加内容
          currentMessage.value += chunk.content
          aiMessage.content = currentMessage.value
        } else if (chunk.type === 'complete') {
          // 完成
          isStreaming.value = false
          if (chunk.answer) {
            aiMessage.content = chunk.answer
          }
          if (chunk.retrieved_docs) {
            aiMessage.retrieved_docs = chunk.retrieved_docs
          }
          if (chunk.thinking_process) {
            aiMessage.thinking_process = chunk.thinking_process
          }
          currentMessage.value = ''
          
          // 消息完成后，重新获取会话列表以同步后端的最新计数
          // 这样可以确保计数与数据库中的实际值一致
          if (currentSessionId.value) {
            // 异步更新，不阻塞 UI
            fetchSessions().catch(err => {
              console.error('更新会话列表失败:', err)
            })
          }
        } else if (chunk.type === 'error') {
          // 错误
          isStreaming.value = false
          aiMessage.content = `错误: ${chunk.message || '未知错误'}`
          currentMessage.value = ''
        }
      },
      (error) => {
        isStreaming.value = false
        aiMessage.content = `错误: ${error.message}`
        currentMessage.value = ''
      }
    )
  }

  /**
   * 更新会话的消息计数
   */
  function updateSessionMessageCount(sessionId: string, increment: number = 1): void {
    const session = sessions.value.find(s => s.session_id === sessionId)
    if (session) {
      session.message_count = (session.message_count || 0) + increment
    }
  }

  /**
   * 停止流式输出
   */
  function stopStreaming(): void {
    if (streamingController.value) {
      streamingController.value.close()
      streamingController.value = null
      isStreaming.value = false
    }
  }

  /**
   * 删除会话
   */
  async function deleteSession(sessionId: string): Promise<void> {
    await chatApi.deleteSession(sessionId)
    sessions.value = sessions.value.filter(s => s.session_id !== sessionId)
    
    if (currentSessionId.value === sessionId) {
      currentSessionId.value = null
      messages.value = []
    }
  }

  /**
   * 新建对话
   */
  function newChat(): void {
    currentSessionId.value = null
    messages.value = []
    currentMessage.value = ''
    stopStreaming()
  }

  return {
    currentSessionId,
    sessions,
    messages,
    currentMessage,
    isStreaming,
    currentSession,
    fetchSessions,
    createSession,
    selectSession,
    fetchSessionMessages,
    sendMessage,
    stopStreaming,
    deleteSession,
    newChat,
    updateSessionMessageCount,
    updateSessionMessageCountFromMessages
  }
})
