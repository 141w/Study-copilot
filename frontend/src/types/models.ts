/**
 * Core Data Models
 */

export interface User {
  id: string
  username: string
  email: string
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
  created_at: string
  chunk_count?: number
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
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  result?: any
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
  /** GET /config/llm 返回：是否已保存 Key + 掩码展示值 */
  has_api_key?: boolean
  api_key_masked?: string
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
