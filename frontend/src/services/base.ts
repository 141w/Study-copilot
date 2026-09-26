/**
 * 部署基址（base path）统一出口。
 *
 * 背景：应用可能要挂在子路径下（例如与个人站共用域名和证书时挂 /study/）。
 * Vite 的 `base` 只管静态资源，**运行时拼出来的 URL 不归它管**——fetch、
 * WebSocket、window.open 里的绝对路径必须自己带前缀，否则页面能打开但
 * 一发请求就 404。所以全站只从这里取前缀，不允许再写裸 '/api'。
 *
 * 本地开发 base 为 '/'，`strip` 后为空串，行为与从前完全一致。
 */

/** Vite 注入的基址，始终以 '/' 结尾，如 '/' 或 '/study/' */
export const BASE_URL: string = import.meta.env.BASE_URL || '/'

/** 去掉尾部斜杠：'/' → ''，'/study/' → '/study/'→'/study' */
const BASE_PREFIX: string = BASE_URL.replace(/\/$/, '')

/** API 前缀：'' + '/api' 或 '/study' + '/api' */
export const API_BASE: string = `${BASE_PREFIX}/api`

/** 给站内绝对路径加上部署前缀。已是绝对 URL（http…）的原样返回。 */
export function withBase(path: string): string {
  if (/^https?:\/\//.test(path)) return path
  if (!path.startsWith('/')) return path
  return `${BASE_PREFIX}${path}`
}
