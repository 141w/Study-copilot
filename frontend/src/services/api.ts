import axios, { type AxiosInstance, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { useToastStore } from '../stores/toast'

// Extend AxiosRequestConfig to include _retry
declare module 'axios' {
  interface InternalAxiosRequestConfig {
    _retry?: boolean
  }
}

const api: AxiosInstance = axios.create({
  baseURL: '/api'
})

// ── Request dedup (idempotent GET/HEAD only) ──────────────────────────────

const _pending = new Map<string, Promise<AxiosResponse>>()

function _dedupKey(config: InternalAxiosRequestConfig): string {
  return `${config.method || 'get'}:${config.url}`
}

function _isIdempotent(method: string | undefined): boolean {
  return ['get', 'head'].includes((method || 'get').toLowerCase())
}

// Override request() to dedup concurrent idempotent calls
const _requestImpl = async function (config: InternalAxiosRequestConfig) {
  const _origRequest = api.request.bind(api)
  if (_isIdempotent(config.method)) {
    const key = _dedupKey(config)
    const existing = _pending.get(key)
    if (existing) return existing
    const pending = _origRequest(config).finally(() => _pending.delete(key))
    _pending.set(key, pending)
    return pending
  }
  return _origRequest(config)
}
;(api as any).request = _requestImpl

// ── Abort controller registry (GET cleanup) ───────────────────────────────

const _aborts = new Map<string, AbortController>()

/** Cancel a specific pending GET by method+url match (supports wildcard *). */
function cancelGet(pattern: string): void {
  for (const [key, ctrl] of _aborts) {
    if (key === pattern || pattern === '*') {
      ctrl.abort()
      _aborts.delete(key)
    }
  }
}

/** Cancel all pending requests (dedup + GET + non-GET). */
function cancelAll(): void {
  for (const [, ctrl] of _aborts) {
    try { ctrl.abort() } catch { /* noop */ }
  }
  _aborts.clear()
}

// ── Auth interceptor ──────────────────────────────────────────────────────

api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// ── Response interceptor (retry + toast) ───────────────────────────────────

api.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error) => {
    const toast = useToastStore()
    const originalRequest = error.config as InternalAxiosRequestConfig
    if (!originalRequest) return Promise.reject(error)

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true

      const refreshToken = localStorage.getItem('refreshToken')
      if (refreshToken) {
        try {
          const response = await axios.post('/api/auth/refresh', {}, {
            headers: { Authorization: `Bearer ${refreshToken}` }
          })

          localStorage.setItem('token', response.data.access_token)
          localStorage.setItem('refreshToken', response.data.refresh_token)

          originalRequest.headers.Authorization = `Bearer ${response.data.access_token}`
          return api(originalRequest)
        } catch (e) {
          localStorage.removeItem('token')
          localStorage.removeItem('refreshToken')
          window.location.href = '/login'
        }
      }
    }

    // Rate limit (429) / temporary server error (503): retry once with backoff
    if ((error.response?.status === 429 || error.response?.status === 503)
        && !originalRequest._retry) {
      originalRequest._retry = true
      const retryAfter = parseInt(error.response.headers['retry-after'] || '0', 10)
      const delay = error.response?.status === 429
        ? (isNaN(retryAfter) || retryAfter <= 0 ? 3000 : retryAfter * 1000)
        : 2000
      await new Promise(r => setTimeout(r, delay))
      return api(originalRequest)
    }

    if (error.response?.data?.detail) {
      toast.error(error.response.data.detail)
    } else if (error.message) {
      toast.error(error.message)
    }

    return Promise.reject(error)
  }
)

export { cancelAll, cancelGet }
export type RequestDedup = typeof _pending
export type AbortRegistry = typeof _aborts
export default api
