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
   * 重置会话相关状态（用于用户切换/登出）
   */
  function resetState(): void {
    currentSessionId.value = null
    sessions.value = []
    messages.value = []
    currentMessage.value = ''
    stopStreaming()
  }

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
   * 拉取会话并自动选中最近一条（若存在）
   * 用于登录后或页面初始加载
   */
  async function loadLatestSession(): Promise<void> {
    await fetchSessions()
    if (sessions.value.length > 0) {
      const latest = sessions.value[0]
      await selectSession(latest.session_id)
    } else {
      newChat()
    }
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
   * 删除消息（乐观更新）
   */
  async function deleteMessage(messageId: number): Promise<void> {
    const index = messages.value.findIndex(m => m.message_id === messageId)
    if (index === -1) return
    
    const removed = messages.value[index]
    messages.value.splice(index, 1)
    updateSessionMessageCountFromMessages(removed.session_id)
    
    try {
      await chatApi.deleteMessage(removed.session_id, messageId)
      // 异步刷新会话列表同步计数
      fetchSessions().catch(err => console.error('刷新会话列表失败:', err))
    } catch (error: any) {
      // 回滚
      messages.value.splice(index, 0, removed)
      updateSessionMessageCountFromMessages(removed.session_id)
      throw new Error(error.message || '删除消息失败，请稍后重试')
    }
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
   * 删除会话（乐观更新）
   * 立即从 UI 移除，后台异步删除
   */
  async function deleteSession(sessionId: string): Promise<void> {
    // 乐观更新：立即从列表中移除（UI 立即响应）
    const sessionToDelete = sessions.value.find(s => s.session_id === sessionId)
    sessions.value = sessions.value.filter(s => s.session_id !== sessionId)
    
    // 如果删除的是当前会话，立即切换到新会话或清空
    if (currentSessionId.value === sessionId) {
      currentSessionId.value = null
      messages.value = []
    }
    
    // 后台异步调用 API 删除（不阻塞 UI）
    try {
      await chatApi.deleteSession(sessionId)
      // 删除成功，无需额外操作（已在乐观更新中处理）
    } catch (error: any) {
      // 删除失败，恢复会话到列表（回滚乐观更新）
      if (sessionToDelete) {
        sessions.value.push(sessionToDelete)
        // 按时间排序（保持原有顺序）
        sessions.value.sort((a, b) => {
          const timeA = a.created_at ? new Date(a.created_at).getTime() : 0
          const timeB = b.created_at ? new Date(b.created_at).getTime() : 0
          return timeB - timeA
        })
      }
      
      // 显示错误提示
      console.error('删除会话失败:', error)
      throw new Error(error.message || '删除会话失败，请稍后重试')
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
    loadLatestSession,
    createSession,
    selectSession,
    fetchSessionMessages,
    sendMessage,
    deleteMessage,
    stopStreaming,
    deleteSession,
    newChat,
    resetState,
    updateSessionMessageCount,
    updateSessionMessageCountFromMessages
  }
})
