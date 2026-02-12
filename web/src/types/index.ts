/* ---- API 通用响应 ---- */

export interface ApiResponse<T> {
  code: number
  data: T | null
  msg: string
}

export interface PaginatedData<T> {
  items: T[]
  total: number
}

/* ---- Auth ---- */

export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  username: string
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface UserInfo {
  id: number
  username: string
  email: string
  is_active: boolean
  created_at: string
}

/* ---- Chat ---- */

export type ConversationStatus =
  | 'active'
  | 'waiting_follow_up'
  | 'completed'
  | 'failed'

export interface Conversation {
  id: number
  title: string
  status: ConversationStatus
  created_at: string
  updated_at: string
}

export interface Message {
  role: 'user' | 'assistant'
  content: string
  executeResult?: Record<string, unknown>[] | null
}

export interface ConversationDetail {
  id: number
  title: string
  status: ConversationStatus
  created_at: string
  updated_at: string
  messages: Message[]
  sql: string | null
  execute_result: Record<string, unknown>[] | null
  error_code: string | null
  error_message: string | null
  follow_up_question: string | null
}

export interface SchemaSyncResult {
  table_count: number
}

/* ---- Node Progress ---- */

export type NodeStatus = 'running' | 'completed' | 'failed'

export interface NodeStep {
  node: string
  label: string
  status: NodeStatus
  startTime: number
  elapsedMs: number | null
}

/* ---- SSE Events ---- */

export interface SSENodeStart {
  node: string
}

export interface SSENodeComplete {
  node: string
}

export interface SSEFollowUp {
  question: string
}

export interface SSEResult {
  sql: string | null
  summary: string | null
  execute_result: Record<string, unknown>[] | null
}

export interface SSEError {
  error_code?: string | null
  error_message?: string | null
}
