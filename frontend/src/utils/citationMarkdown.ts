/**
 * 引用标记 [来源N] 的 Markdown 安全管线。
 *
 * 机制（保持 [来源N] 协议，不引入 <kb> 标签）：
 * 1. 解析前把 [来源N] 换成 markdown-it 不会解析的占位符，解析后再还原为角标 HTML；
 * 2. 流式尾部隐藏尚未闭合的 [来源… 残缺标记，避免闪现半截角标。
 */

export const CITATION_BADGE_CLASS = 'source-badge'

/** 完整引用标记：[来源1] [来源12] … */
const CITATION_RE = /\[来源(\d+)\]/g

/** 流式尾部残缺标记：[来源 / [来源1 / [来源12 …（无右括号，允许尾随空白/CR） */
const INCOMPLETE_TAIL_RE = /\[来源\d*\s*$/

/**
 * 占位符用 Unicode 私有区字符包夹：
 * markdown-it 不会把它当成链接标签 / 强调 / 自动链接，从而原样穿过解析器。
 */
const PH_OPEN = '\uE000'
const PH_CLOSE = '\uE001'
const PH_RE = /\uE000SC(\d+)\uE001/g

/** 流式期间隐藏正文尾部尚未闭合的 [来源… 标记 */
export function hideIncompleteCitationTail(text: string, isStreaming = false): string {
  if (!text || !isStreaming) return text || ''
  return text.replace(INCOMPLETE_TAIL_RE, '')
}

/** 解析前：[来源N] → 占位符（先抽出围栏/行内代码，避免把代码里的字面标记变成角标） */
const CODE_STASH_RE = /(```[\s\S]*?```|`[^`\n]+`)/g
const CODE_STASH: string[] = []

export function swapCitationsForPlaceholders(text: string): string {
  if (!text) return ''
  CODE_STASH.length = 0
  const stashed = text.replace(CODE_STASH_RE, m => {
    CODE_STASH.push(m)
    return `${PH_OPEN}CODE${CODE_STASH.length - 1}${PH_CLOSE}`
  })
  return stashed.replace(
    CITATION_RE,
    (_match, num: string) => `${PH_OPEN}SC${num}${PH_CLOSE}`
  )
}

/** 生成可点击角标 HTML（与既有 .source-badge 契约一致；仅接受纯数字） */
export function makeCitationBadge(num: string | number): string {
  const n = String(num)
  if (!/^\d+$/.test(n)) return ''
  return `<sup class="${CITATION_BADGE_CLASS}" data-index="${n}">[${n}]</sup>`
}

/**
 * 解析后：占位符 → 角标 HTML。
 * 同时兜底还原 HTML 中残留的字面 [来源N]（历史缓存 / 外部拼接的已渲染片段）。
 */
export function restoreCitationPlaceholders(html: string): string {
  if (!html) return ''
  let out = html.replace(PH_RE, (_match, num: string) => makeCitationBadge(num))
  // 还原代码块占位
  out = out.replace(
    new RegExp(`${PH_OPEN}CODE(\\d+)${PH_CLOSE}`, 'g'),
    (_m, i: string) => CODE_STASH[Number(i)] ?? ''
  )
  out = out.replace(/\[来源(\d+)\]/g, (_match, num: string) => makeCitationBadge(num))
  return out
}

/** markdown 解析前准备：隐藏流式残缺标记 + 换出占位符 */
export function prepareCitationMarkdown(text: string, isStreaming = false): string {
  return swapCitationsForPlaceholders(hideIncompleteCitationTail(text, isStreaming))
}

/** markdown 解析后收尾：还原为角标 */
export function finalizeCitationHtml(html: string): string {
  return restoreCitationPlaceholders(html)
}
