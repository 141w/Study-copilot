/**
 * 通用格式化工具（P2-1）。
 *
 * 此前 formatDate 在 HomeView / ChatHistoryPanel / NoteCard / TaskPanel
 * 有 4 份平行实现（阈值与措辞各不相同），formatSize/cleanText 分散在
 * DocumentView。收敛为单一可测实现。
 */

/** 相对时间：刚刚 / N分钟前 / N小时前 / 昨天 / N天前 / 短日期 */
export function formatRelativeTime(dateStr?: string | null): string {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = Date.now()
  const diff = now - date.getTime()
  if (diff < 0) return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })

  if (diff < 60_000) return '刚刚'
  if (diff < 3_600_000) return Math.floor(diff / 60_000) + ' 分钟前'
  if (diff < 86_400_000) return Math.floor(diff / 3_600_000) + ' 小时前'
  if (diff < 172_800_000) return '昨天'
  if (diff < 604_800_000) return Math.floor(diff / 86_400_000) + ' 天前'
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

/** Home 历史记录用的简化相对时间（今天/昨天/N天前/短日期） */
export function formatDayLabel(dateStr?: string | null): string {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const diff = Date.now() - date.getTime()
  if (diff < 86_400_000) return '今天'
  if (diff < 172_800_000) return '昨天'
  if (diff < 604_800_000) return Math.floor(diff / 86_400_000) + '天前'
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

/** 文件大小：字节数 → 人类可读 */
export function formatSize(bytes?: number | null): string {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  while (bytes >= 1024 && i < units.length - 1) {
    bytes /= 1024
    i++
  }
  return `${bytes.toFixed(1)} ${units[i]}`
}

/** 时间部分：HH:mm */
export function formatTime(timeStr?: string | null): string {
  if (!timeStr) return ''
  const d = new Date(timeStr)
  // Invalid Date 的 getTime() 为 NaN；jsdom/浏览器下 toLocaleTimeString
  // 不抛异常而返回 "Invalid Date" 字符串，需显式检测
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

/**
 * PDF 提取文本清理：单换行替换为空格，保留段落分隔。
 */
export function cleanPdfText(text?: string | null): string {
  if (!text) return ''
  return text.replace(/([^。!?！？])\n([^。!?！？])/g, '$1 $2').trim()
}

/** Composable 形式（与项目 composable 约定一致） */
export function useFormat() {
  return {
    formatRelativeTime,
    formatDayLabel,
    formatSize,
    formatTime,
    cleanPdfText
  }
}
