/**
 * 统一时间戳解析（F4）。
 *
 * 后端历史序列化是 naive UTC 空格分隔串（`str(datetime)` → "2026-09-29 03:24:11.123"），
 * 以及标准 ISO 8601（带 Z 或 ±HH:MM）。禁止各处裸 `new Date(...)`：
 * 空格格式在部分引擎按本地时区解释（偏 8 小时），Safari 甚至返回 Invalid Date。
 */

/** 后端旧格式（naive UTC）：`YYYY-MM-DD HH:MM:SS[.fff]` */
const NAIVE_UTC = /^(\d{4}-\d{2}-\d{2})[ ](\d{2}:\d{2}:\d{2}(?:\.\d+)?)$/

/**
 * 解析时间戳为 Date；失败返回 null（调用方显示原始串，不得出现 Invalid Date）。
 *
 * 规则：
 * - `YYYY-MM-DD HH:MM:SS[.fff]` → 按 UTC 解析（后端 naive UTC 语义）
 * - 其余交给 `new Date`（含 ISO 8601 带时区标记）
 */
export function parseTimestamp(ts: string | null | undefined): Date | null {
  if (!ts || typeof ts !== 'string') return null
  const s = ts.trim()
  if (!s) return null

  const m = NAIVE_UTC.exec(s)
  if (m) {
    const iso = `${m[1]}T${m[2]}Z`
    const d = new Date(iso)
    return Number.isFinite(d.getTime()) ? d : null
  }

  const d = new Date(s)
  return Number.isFinite(d.getTime()) ? d : null
}

/**
 * 本地日边界分组：today / yesterday / week / older。
 * 边界按**用户本地时区**的 0 点计算，不是 UTC 0 点。
 */
export function localDayKey(
  ts: string | null | undefined
): 'today' | 'yesterday' | 'week' | 'older' {
  const d = parseTimestamp(ts)
  if (!d) return 'older'
  const now = new Date()
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const t = d.getTime()
  if (t >= startOfToday) return 'today'
  if (t >= startOfToday - 86400000) return 'yesterday'
  if (t >= startOfToday - 7 * 86400000) return 'week'
  return 'older'
}
