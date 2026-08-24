/**
 * 对话导出为 Markdown 的纯函数集合。
 * 与视图解耦以便单测（标题回退、来源清单格式）。
 */

export interface ExportableSource {
  source?: string
  page?: string
  text?: string
}

export interface ExportableChatMessage {
  role: string
  content: string
  sources?: ExportableSource[]
}

/** 将消息列表渲染为 Markdown 文本 */
export function buildChatMarkdown(
  messages: ExportableChatMessage[],
  title: string,
): string {
  let md = `# ${title || '对话'}\n\n`

  for (const msg of messages) {
    if (msg.role === 'user') {
      md += `## 用户\n\n${msg.content}\n\n`
    } else if (msg.role === 'assistant') {
      md += `## AI\n\n${msg.content}\n\n`
      if (msg.sources && msg.sources.length > 0) {
        md += `## 参考来源\n\n`
        msg.sources.forEach((source, idx) => {
          const src = source.source || '未知来源'
          const page = source.page ? ` P${source.page}` : ''
          const text = source.text ? ` — ${source.text}` : ''
          md += `${idx + 1}. ${src}${page}${text}\n`
        })
        md += '\n'
      }
    }
  }
  return md
}

/** 触发浏览器下载（DOM 副作用，独立于纯函数便于测试） */
export function downloadChatMarkdown(markdown: string, filename?: string): void {
  const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  const date = new Date().toISOString().slice(0, 10)
  a.href = url
  a.download = filename || `chat-${date}.md`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
