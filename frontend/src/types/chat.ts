/**
 * 聊天相关类型定义
 */

export interface Message {
  id?: string
  message_id?: number
  session_id: string
  role: 'user' | 'assistant'
  content: string
  created_at?: string
  retrieved_docs?: RetrievedDoc[]
  thinking_process?: ThinkingStep[]
}

export interface RetrievedDoc {
  chunk_id?: number
  content: string
  similarity?: number
  metadata?: Record<string, any>
}

export interface ThinkingStep {
  step: number
  action: string
  description: string
  details?: string
}

export interface Session {
  session_id: string
  title: string
  created_at?: string
  message_count: number
}

export interface ChatMessageRequest {
  message: string
  session_id?: string
}

export interface SSEChunk {
  type: 'chunk' | 'complete' | 'error' | 'thinking'
  content?: string
  answer?: string
  session_id?: string
  retrieved_docs?: RetrievedDoc[]
  thinking_process?: ThinkingStep[]
  message?: string
  data?: any
  tokens_used?: number
}
