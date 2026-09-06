/**
 * Core Data Models
 */

export interface User {
  id: string
  username: string
  email: string
  /** 注册时间（GET/PUT /auth/me 返回，ProfileView 展示用） */
  created_at?: string
}

export interface AuthTokens {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface Document {
  id: string
  filename: string
  status: 'processing' | 'ready' | 'error'
  created_at?: string
  chunk_count?: number
  /** 字节大小（列表接口返回；DocumentView 格式化展示用） */
  file_size?: number
}

export interface Source {
  index: number
  text: string
  page?: string
  document_id?: string
  source?: string
  relevance_score?: number
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  thinking?: string
  isStreaming?: boolean
  expandedSources?: boolean
  timestamp?: string
}

export interface ChatSession {
  id: string
  title: string
  created_at: string
  message_count?: number
}

export interface Note {
  id: string
  title: string
  content: string
  note_type: 'markdown' | 'plain'
  course_space_id?: string
  is_pinned?: boolean
  tags: string[]
  created_at: string
  updated_at: string
}

export interface Course {
  id: string
  name: string
  description?: string
  color?: string
  created_at: string
  document_count?: number
  note_count?: number
}

export interface Quiz {
  id: string
  question_type: 'choice' | 'short_answer'
  question: string
  options?: string[] | null
  answer?: string | null
  explanation?: string | null
  document_id?: string
}

export interface QuizResult {
  id: string
  quiz_id: string
  score: number
  total: number
  answers: AnswerResult[]
  created_at: string
}

export interface AnswerResult {
  question_id: string
  user_answer: string
  correct_answer: string
  is_correct: boolean
  explanation?: string
}

export interface Task {
  id: string
  task_type: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  progress: number
  /** 任务结果负载（document_process/quiz_generate/tts_generate 等各异） */
  result?: Record<string, unknown>
  error?: string
  created_at: string
  completed_at?: string
}

export interface LLMConfig {
  id?: string
  provider: string
  /** 保存时提交用；GET 响应永不返回明文（安全修复 2026-08-19） */
  api_key?: string
  base_url?: string
  model_name: string
  temperature?: number
  max_tokens?: number
  embedding_model?: string
  embedding_dimension?: number
  message_format?: string
  /** 模型上下文窗口大小（默认 256k = 262144） */
  context_window?: number
  /** GET /config/llm 返回：是否已保存 Key + 掩码展示值 */
  has_api_key?: boolean
  api_key_masked?: string
}

export interface SystemStatus {
  database: {
    status: string
    document_chunks: number
    pgvector_dimension: number
  }
  vector_engine: {
    name: string
    model_name: string
    dimension: number
    device: string
    is_ready: boolean
  }
  timestamp: string
}

export interface LLMCapabilities {
  success: boolean
  context_window: number
  max_output_tokens: number
  source: 'vendor_api' | 'vendor_spec' | 'default_256k'
  model_name: string
  latency_ms?: number
  message?: string
}

export interface Transformation {
  key: string
  name: string
  name_en: string
  description: string
}

export interface Tag {
  id: string
  name: string
  color?: string
}
