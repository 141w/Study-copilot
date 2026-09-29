/**
 * 401 认证错误策略（纯函数，便于单测；api.ts 拦截器消费）。
 */

/**
 * 401 是否应弹 toast。
 *
 * 认证失败统一不弹：登录/改密等表单在页内展示错误；会话过期由
 * authRefresh 弹「登录已过期」；未登录调受保护接口应静默（路由守卫负责跳转）。
 * 避免打开公共首页时弹出 FastAPI 英文 "Not authenticated"。
 */
export function shouldToastAuthError(status: number | undefined): boolean {
  return status !== 401
}

/**
 * 该 401 是否属于「会话失效」（应尝试 refresh / 踢登录），
 * 而非登录密码错误、原密码错误等表单业务错误。
 */
export function isSessionExpiredDetail(detail: unknown): boolean {
  if (typeof detail !== 'string' || !detail) return true
  const sessionDetails = new Set([
    'Not authenticated',
    '无法验证凭据',
    '无效的访问令牌类型',
    '账户已被禁用',
    '用户已被禁用'
  ])
  return sessionDetails.has(detail)
}
