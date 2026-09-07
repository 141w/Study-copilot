import { describe, it, expect } from 'vitest'
import { useMarkdown, normalizeMarkdownNewlines } from '@/composables/useMarkdown'

describe('useMarkdown & normalizeMarkdownNewlines', () => {
  const { renderMarkdown, stripMarkdown, getExcerpt } = useMarkdown()

  it('普通文本中的裸露字面量 \\n 转换为真实换行符', () => {
    const raw = '第一行\\n第二行\\n第三行'
    const normalized = normalizeMarkdownNewlines(raw)
    expect(normalized).toBe('第一行\n第二行\n第三行')
  })

  it('普通文本中的 \\r\\n 转换为真实换行符', () => {
    const raw = '首行\\r\\n次行'
    const normalized = normalizeMarkdownNewlines(raw)
    expect(normalized).toBe('首行\n次行')
  })

  it('严格保护三反引号多行代码块内部的 \\n 原样保留', () => {
    const code = '这是正文\\n```python\nprint("hello\\nworld")\n```\\n这是后续正文'
    const normalized = normalizeMarkdownNewlines(code)
    expect(normalized).toContain('这是正文\n```python\nprint("hello\\nworld")\n```\n这是后续正文')
    expect(normalized).toContain('print("hello\\nworld")')
  })

  it('严格保护行内单反引号代码内部的 \\n 原样保留', () => {
    const inline = '请注意 `\\n` 是换行转义符\\n第二行说明'
    const normalized = normalizeMarkdownNewlines(inline)
    expect(normalized).toBe('请注意 `\\n` 是换行转义符\n第二行说明')
  })

  it('markdown-it 启用 breaks: true，单换行自动转为 <br>', () => {
    const input = '第一行\n第二行'
    const html = renderMarkdown(input)
    expect(html).toContain('<br>')
  })

  it('renderMarkdown 自动清除裸露 \\n 并正确渲染 HTML', () => {
    const input = '核心论点一\\n\\n核心论点二'
    const html = renderMarkdown(input)
    expect(html).not.toContain('\\n')
    expect(html).toContain('<p>核心论点一</p>')
    expect(html).toContain('<p>核心论点二</p>')
  })

  it('stripMarkdown 与 getExcerpt 正常运行', () => {
    const md = '## 标题\n**加粗内容** 与 [链接](http://example.com)'
    expect(stripMarkdown(md)).toBe('标题\n加粗内容 与 链接')
    expect(getExcerpt(md, 5)).toBe('标题\n加粗...')
  })
})
