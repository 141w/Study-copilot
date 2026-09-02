import axios, { type AxiosInstance, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { useToastStore } from '../stores/toast'
import { refreshAccessToken, redirectToLogin } from './authRefresh'

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
// _origRequest must be captured BEFORE the override to avoid infinite recursion
const _origRequest = api.request.bind(api)
const _requestImpl = async function (config: InternalAxiosRequestConfig) {
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

function _cancelMatches(pattern: string): void {
  for (const [key, ctrl] of _aborts) {
    if (key === pattern || pattern === '*') {
      ctrl.abort()
      _aborts.delete(key)
    }
  }
}

/** Cancel all pending requests. Call on route change / component unmount. */
function cancelAll(): void {
  for (const [, ctrl] of _aborts) {
    try { ctrl.abort() } catch { /* noop */ }
  }
  _aborts.clear()
}

/** Cancel pending GETs matching pattern (supports wildcard '*'). */
function cancelGet(pattern: string): void {
  _cancelMatches(pattern)
}

export { cancelAll, cancelGet }

// ── Request interceptor (auth + abort signal + dedup) ──────────────────────

api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // Register AbortController so cancelAll() can reach in-flight requests
    if (!config.signal) {
      const key = `${config.method || 'get'}:${config.url}`
      const ctrl = new AbortController()
      _aborts.set(key, ctrl)
      config.signal = ctrl.signal
    }
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    // If request was aborted via cancelAll, the original controller
    // is already removed from _aborts — nothing to clean up here
    return Promise.reject(error)
  }
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

      // P1-3：复用共享 refreshAccessToken（与 chat.ts SSE 路径同源）
      const outcome = await refreshAccessToken()
      if (outcome.ok && outcome.accessToken) {
        originalRequest.headers.Authorization = `Bearer ${outcome.accessToken}`
        return api(originalRequest)
      }
      redirectToLogin()
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

export default api
