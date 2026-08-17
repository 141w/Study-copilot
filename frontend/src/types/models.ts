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
  page?: number
  document_id?: string
  document_name?: string
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
  document_id: string
  created_at: string
  updated_at: string
  message_count?: number
}

export interface Note {
  id: string
  title: string
  content: string
  note_type: 'manual' | 'ai'
  course_id?: string
  document_id?: string
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
  document_id: string
  questions: Question[]
  created_at: string
}

export interface Question {
  id: string
  type: 'multiple_choice' | 'short_answer'
  question: string
  options?: string[]
  answer: string
  explanation?: string
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
  provider: string
  api_key: string
  base_url: string
  model_name: string
  temperature?: number
  max_tokens?: number
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
