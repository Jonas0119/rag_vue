/**
 * 聊天 API 客户端
 */
import type { Session, Message, ChatMessageRequest, SSEChunk } from '@/types/chat'

export const chatApi = {
  /**
   * 发送消息（使用 POST + SSE）
   * 返回一个可关闭的控制器对象
   */
  sendMessage(
    request: ChatMessageRequest,
    onMessage: (chunk: SSEChunk) => void,
    onError?: (error: Error) => void
  ): { close: () => void } {
    const token = localStorage.getItem('token')
    if (!token) {
      throw new Error('未登录')
    }

    const controller = new AbortController()
    
    fetch('/api/chat/message', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
        'Accept': 'text/event-stream'
      },
      body: JSON.stringify(request),
      signal: controller.signal
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }

        const reader = response.body?.getReader()
        const decoder = new TextDecoder()

        if (!reader) {
          throw new Error('无法读取响应流')
        }

        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          
          if (done) {
            break
          }

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6)) as SSEChunk
                onMessage(data)
              } catch (e) {
                console.error('解析 SSE 数据失败:', e)
              }
            }
          }
        }
      })
      .catch((error) => {
        if (error.name !== 'AbortError' && onError) {
          onError(error)
        }
      })

    return {
      close: () => controller.abort()
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
  }
}
