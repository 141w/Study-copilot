/**
 * 共享的 401 token 刷新逻辑（P1-3）。
 *
 * 此前存在两份并行实现：
 *  - services/api.ts 响应拦截器（axios 请求路径）
 *  - stores/chat.ts askQuestionStream 内部（fetch SSE 路径，因不经过 axios）
 * 行为易漂移（曾漂移过），故抽为单一实现。
 *
 * 刷新成功：写回 localStorage 并返回新 access token。
 * 刷新失败：清除凭证并返回 null（调用方自行决定跳转登录）。
 */

export interface RefreshOutcome {
  ok: boolean
  accessToken?: string
}

export async function refreshAccessToken(): Promise<RefreshOutcome> {
  const refreshToken = localStorage.getItem('refreshToken')
  if (!refreshToken) return { ok: false }

  try {
    const resp = await fetch('/api/auth/refresh', {
      method: 'POST',
      headers: { Authorization: `Bearer ${refreshToken}` }
    })
    if (!resp.ok) throw new Error(`refresh failed: ${resp.status}`)

    const data = (await resp.json()) as {
      access_token: string
      refresh_token: string
    }
    localStorage.setItem('token', data.access_token)
    localStorage.setItem('refreshToken', data.refresh_token)
    return { ok: true, accessToken: data.access_token }
  } catch {
    localStorage.removeItem('token')
    localStorage.removeItem('refreshToken')
    return { ok: false }
  }
}

/** 判定是否应跳转登录页（刷新失败后调用） */
export function redirectToLogin(): void {
  try {
    // 动态 import 避免 services ↔ router 循环依赖
    import('../router').then(({ default: router }) => {
      router.push({ path: '/login', query: { redirect: window.location.pathname } })
    })
  } catch {
    window.location.href = '/login'
  }
}
