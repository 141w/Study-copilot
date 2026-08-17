/**
 * API Response Types
 */

export interface ApiResponse<T = any> {
  data: T
  message?: string
}

export interface ApiError {
  detail: string
  status_code?: number
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}
