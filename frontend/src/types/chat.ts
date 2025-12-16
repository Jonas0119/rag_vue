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
  type: 'chunk' | 'complete' | 'error' | 'thinking' | 
        'node_start' | 'node_progress' | 'node_complete' | 'status'
  content?: string
  answer?: string
  session_id?: string
  retrieved_docs?: RetrievedDoc[]
  thinking_process?: ThinkingStep[]
  message?: string
  data?: any
  tokens_used?: number
  
  // 新增字段（用于节点状态事件）
  node?: string           // 节点名称
  node_name?: string     // 节点友好名称
  description?: string   // 节点描述
  result?: any           // 节点执行结果
  timestamp?: number     // 时间戳
  progress?: number      // 进度百分比（0-100）
}
