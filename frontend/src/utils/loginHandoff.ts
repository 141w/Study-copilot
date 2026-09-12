/**
 * 登录成功 → 首页 logo 的共享元素交接。
 * LoginView 捕获 bot 旧 rect 后导航；AppHeader 挂载时取出并做 FLIP。
 */
let pendingRect: DOMRect | null = null

export function setLoginHandoffRect(rect: DOMRect | null): void {
  pendingRect = rect
}

export function takeLoginHandoffRect(): DOMRect | null {
  const rect = pendingRect
  pendingRect = null
  return rect
}
