/**
 * 聊天 API 客户端
 */
import type { Session, Message, ChatMessageRequest } from '@/types/chat'

export const chatApi = {
  /**
   * 发送消息（普通 POST 请求）
   * 返回后端的简单确认结果
   */
  async sendMessage(
    request: ChatMessageRequest
  ): Promise<{ success: boolean; session_id: string }> {
    const token = localStorage.getItem('token')
    if (!token) {
      throw new Error('未登录')
    }

    const response = await fetch('/api/chat/message', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(request)
    })

    if (!response.ok) {
      const text = await response.text()
      throw new Error(text || `HTTP error! status: ${response.status}`)
    }

    const data = await response.json()
    return {
      success: !!data.success,
      session_id: data.session_id as string
    }
  },

  /**
   * 获取会话列表
   */
  async getSessions(): Promise<Session[]> {
    const response = await fetch('/api/chat/sessions', {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      }
    })
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    return response.json()
  },

  /**
   * 创建新会话
   */
  async createSession(title?: string): Promise<Session> {
    const response = await fetch('/api/chat/sessions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
      body: JSON.stringify({ title })
    })
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    return response.json()
  },

  /**
   * 删除会话
   */
  async deleteSession(sessionId: string): Promise<void> {
    const response = await fetch(`/api/chat/sessions/${sessionId}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      }
    })
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
  },

  /**
   * 获取会话消息
   */
  async getSessionMessages(sessionId: string): Promise<Message[]> {
    const response = await fetch(`/api/chat/sessions/${sessionId}/messages`, {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      }
    })
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    return response.json()
  },

  /**
   * 删除消息
   */
  async deleteMessage(sessionId: string, messageId: number): Promise<void> {
    const response = await fetch(`/api/chat/sessions/${sessionId}/messages/${messageId}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      }
    })
    
    if (!response.ok) {
      const msg = await response.text()
      throw new Error(msg || `HTTP error! status: ${response.status}`)
    }
  }
}
