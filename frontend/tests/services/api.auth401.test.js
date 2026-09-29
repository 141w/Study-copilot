import { describe, it, expect } from 'vitest'
import { shouldToastAuthError, isSessionExpiredDetail } from '../../src/services/authErrorPolicy'

describe('401 toast / session-expiry decision', () => {
  it('never toasts on 401 (Not authenticated must not pop on public pages)', () => {
    expect(shouldToastAuthError(401)).toBe(false)
  })

  it('still toasts other status codes', () => {
    expect(shouldToastAuthError(404)).toBe(true)
    expect(shouldToastAuthError(422)).toBe(true)
    expect(shouldToastAuthError(500)).toBe(true)
    expect(shouldToastAuthError(undefined)).toBe(true)
  })

  it('treats FastAPI Bearer miss as session expiry', () => {
    expect(isSessionExpiredDetail('Not authenticated')).toBe(true)
    expect(isSessionExpiredDetail(undefined)).toBe(true)
    expect(isSessionExpiredDetail('')).toBe(true)
    expect(isSessionExpiredDetail(null)).toBe(true)
  })

  it('treats JWT invalid as session expiry', () => {
    expect(isSessionExpiredDetail('无法验证凭据')).toBe(true)
    expect(isSessionExpiredDetail('无效的访问令牌类型')).toBe(true)
    expect(isSessionExpiredDetail('账户已被禁用')).toBe(true)
  })

  it('does not treat form credential errors as session expiry', () => {
    expect(isSessionExpiredDetail('用户名或密码错误')).toBe(false)
    expect(isSessionExpiredDetail('原密码不正确')).toBe(false)
    expect(isSessionExpiredDetail('无效的刷新令牌')).toBe(false)
  })
})
