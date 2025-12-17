/**
 * 聊天 Store
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { chatApi } from '@/api/chat'
import type { Message, Session, ChatMessageRequest } from '@/types/chat'

// 节点状态接口
interface NodeStatus {
  node: string
  node_name: string
  description: string
  status: 'pending' | 'running' | 'completed' | 'error'
  progress?: number
  result?: any
  timestamp?: number
}

export const useChatStore = defineStore('chat', () => {
  const currentSessionId = ref<string | null>(null)
  const sessions = ref<Session[]>([])
  const messages = ref<Message[]>([])
  const currentMessage = ref<string>('')
  const isStreaming = ref(false)
  const hasTimeout = ref(false)
  const activeNodes = ref<NodeStatus[]>([])  // 当前执行的节点列表
  const isLoadingMessages = ref(false)       // 会话消息加载中
  // 轮询控制
  let pollingAbort = { aborted: false }

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
    activeNodes.value = []
    hasTimeout.value = false
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
    // 切换会话时，先清空当前消息并进入“加载中”状态，避免短暂显示旧会话内容
    currentSessionId.value = sessionId
    messages.value = []
    currentMessage.value = ''
    activeNodes.value = []
    stopStreaming()
    hasTimeout.value = false

    isLoadingMessages.value = true
    try {
      await fetchSessionMessages(sessionId)
    } finally {
      isLoadingMessages.value = false
    }
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
    // 如果当前没有消息且 session 发生变化，也进入加载状态
    if (!messages.value.length || currentSessionId.value !== sessionId) {
      isLoadingMessages.value = true
    }
    const messageList = await chatApi.getSessionMessages(sessionId)
    messages.value = messageList
    // 获取消息后，更新会话的消息计数
    updateSessionMessageCountFromMessages(sessionId)
    isLoadingMessages.value = false
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

    // 开始后台处理 + 轮询
    isStreaming.value = true
    hasTimeout.value = false
    currentMessage.value = ''
    pollingAbort.aborted = false

    const request: ChatMessageRequest = {
      message,
      session_id: currentSessionId.value
    }

    try {
      await chatApi.sendMessage(request)
      // 后端 / RAG Service 已接受，开始轮询答案
      if (currentSessionId.value) {
        startPollingForAnswer(currentSessionId.value)
      }
    } catch (error: any) {
      console.error('[ChatStore] 发送消息失败:', error)
      isStreaming.value = false
      hasTimeout.value = false
      aiMessage.content = `错误: ${error.message || '发送失败，请稍后重试'}`
    }
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
   * 停止当前“思考中”状态和轮询
   */
  function stopStreaming(): void {
    isStreaming.value = false
    activeNodes.value = []
    pollingAbort.aborted = true
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

  /**
   * 轮询获取回答：10s -> 5s -> 3s -> 每 2s，最长 120s
   */
  async function startPollingForAnswer(sessionId: string): Promise<void> {
    const delays = [10000, 5000, 3000]
    const steadyDelay = 2000
    const maxDuration = 120000
    const startTime = Date.now()
    let delayIndex = 0

    while (true) {
      if (pollingAbort.aborted) {
        return
      }

      const now = Date.now()
      if (now - startTime >= maxDuration) {
        isStreaming.value = false
        hasTimeout.value = true
        return
      }

      const delay = delayIndex < delays.length ? delays[delayIndex] : steadyDelay
      delayIndex += 1

      await new Promise(resolve => setTimeout(resolve, delay))
      if (pollingAbort.aborted) {
        return
      }

      try {
        await fetchSessionMessages(sessionId)
      } catch (error) {
        console.error('[ChatStore] 轮询获取消息失败:', error)
        // 失败时继续下一轮，避免因为偶发错误终止
        continue
      }

      // 检查该会话最新一条消息是否为 assistant 且有内容
      const sessionMessages = messages.value.filter(m => m.session_id === sessionId)
      const last = sessionMessages[sessionMessages.length - 1]
      if (last && last.role === 'assistant' && last.content && last.content.trim()) {
        isStreaming.value = false
        hasTimeout.value = false
        // 异步刷新会话列表同步计数
        fetchSessions().catch(err => console.error('更新会话列表失败:', err))
        return
      }
    }
  }

  /**
   * 在超时时重试上一条用户问题
   */
  async function retryLastQuestion(): Promise<void> {
    if (!currentSessionId.value) return
    const sessionMessages = messages.value.filter(m => m.session_id === currentSessionId.value)
    const lastUser = [...sessionMessages].reverse().find(m => m.role === 'user' && m.content && m.content.trim())
    if (!lastUser) return

    hasTimeout.value = false
    await sendMessage(lastUser.content)
  }

  return {
    currentSessionId,
    sessions,
    messages,
    currentMessage,
    isStreaming,
    hasTimeout,
    activeNodes,
    isLoadingMessages,
    currentSession,
    fetchSessions,
    loadLatestSession,
    createSession,
    selectSession,
    fetchSessionMessages,
    sendMessage,
    retryLastQuestion,
    deleteMessage,
    stopStreaming,
    deleteSession,
    newChat,
    resetState,
    updateSessionMessageCount,
    updateSessionMessageCountFromMessages
  }
})
