import MarkdownIt from 'markdown-it'
// 按需引入：全量 highlight.js 会使 ChatView chunk 膨胀到 ~1MB
import hljs from 'highlight.js/lib/core'
import javascript from 'highlight.js/lib/languages/javascript'
import typescript from 'highlight.js/lib/languages/typescript'
import python from 'highlight.js/lib/languages/python'
import java from 'highlight.js/lib/languages/java'
import json from 'highlight.js/lib/languages/json'
import bash from 'highlight.js/lib/languages/bash'
import sql from 'highlight.js/lib/languages/sql'
import xml from 'highlight.js/lib/languages/xml'
import css from 'highlight.js/lib/languages/css'
import markdownLang from 'highlight.js/lib/languages/markdown'
import yaml from 'highlight.js/lib/languages/yaml'

hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('python', python)
hljs.registerLanguage('java', java)
hljs.registerLanguage('json', json)
hljs.registerLanguage('bash', bash)
hljs.registerLanguage('shell', bash)
hljs.registerLanguage('sql', sql)
hljs.registerLanguage('xml', xml)
hljs.registerLanguage('html', xml)
hljs.registerLanguage('css', css)
hljs.registerLanguage('markdown', markdownLang)
hljs.registerLanguage('yaml', yaml)
// 未注册语言的代码块由下方 highlight() 回退为转义纯文本

// Create markdown-it instance with highlight.js
const md: MarkdownIt = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  breaks: true,
  highlight: function (str: string, lang: string): string {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return '<pre class="hljs"><code>' +
               hljs.highlight(str, { language: lang, ignoreIllegals: true }).value +
               '</code></pre>'
      } catch {}
    }
    // Unknown/failed language: escaped plain-text code block
    return '<pre class="hljs"><code>' + md.utils.escapeHtml(str) + '</code></pre>'
  }
})

/**
 * 将普通 Markdown 文本中可能裸露的字面量 '\n' 或 '\\n' 转换为真实换行符，
 * 同时严格保护三反引号多行代码块及单反引号行内代码内部的原样转义字符不受影响。
 */
export function normalizeMarkdownNewlines(content: string): string {
  if (!content) return ''
  // 规范化物理 CRLF
  let text = content.replace(/\r\n/g, '\n')

  // 若文本中根本不含字面量反斜杠换行 '\n'，直接返回
  if (!text.includes('\\n') && !text.includes('\\r')) {
    return text
  }

  // 保护代码块（包括多行代码块与行内代码）
  const codeBlocks: string[] = []
  const placeholderPrefix = '___MD_CODE_BLOCK_' + Math.random().toString(36).slice(2, 8) + '_'

  // 1. 暂存三反引号代码块（流式可能未闭合）
  text = text.replace(/```[\s\S]*?(?:```|$)/g, (match) => {
    const idx = codeBlocks.length
    codeBlocks.push(match)
    return `${placeholderPrefix}${idx}___`
  })

  // 2. 暂存行内代码块
  text = text.replace(/`[^`\n]*`/g, (match) => {
    const idx = codeBlocks.length
    codeBlocks.push(match)
    return `${placeholderPrefix}${idx}___`
  })

  // 3. 在代码块外部将字面量 '\n' 转换为真实换行
  text = text.replace(/\\r\\n/g, '\n').replace(/\\n/g, '\n')

  // 4. 恢复代码块
  text = text.replace(new RegExp(`${placeholderPrefix}(\\d+)___`, 'g'), (_, idxStr) => {
    const idx = parseInt(idxStr, 10)
    return codeBlocks[idx] ?? ''
  })

  return text
}

/** useMarkdown 返回的渲染工具集 */
export interface MarkdownUtils {
  /** Render markdown string to HTML */
  renderMarkdown: (content: string) => string
  /** Strip markdown formatting and return plain text */
  stripMarkdown: (content: string) => string
  /** Normalize exposed literal newlines */
  normalizeNewlines: (content: string) => string
  /** Get first N characters of plain text from markdown */
  getExcerpt: (content: string, length?: number) => string
  markdownIt: MarkdownIt
}

/**
 * Composable for Markdown rendering
 */
export function useMarkdown(): MarkdownUtils {
  /**
   * Render markdown string to HTML
   */
  function renderMarkdown(content: string): string {
    if (!content) return ''
    return md.render(normalizeMarkdownNewlines(content))
  }

  /**
   * Strip markdown formatting and return plain text
   */
  function stripMarkdown(content: string): string {
    if (!content) return ''
    // Simple stripping - remove common markdown syntax
    return content
      .replace(/#{1,6}\s/g, '') // headers
      .replace(/\*\*(.*?)\*\*/g, '$1') // bold
      .replace(/\*(.*?)\*/g, '$1') // italic
      .replace(/`(.*?)`/g, '$1') // inline code
      .replace(/```[\s\S]*?```/g, '') // code blocks
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1') // links
      .replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1') // images
      .replace(/[-*+]\s/g, '') // list items
      .replace(/\n{2,}/g, '\n\n') // multiple newlines
      .trim()
  }

  /**
   * Get first N characters of plain text from markdown
   */
  function getExcerpt(content: string, length: number = 150): string {
    const plainText = stripMarkdown(content)
    if (plainText.length <= length) return plainText
    return plainText.substring(0, length) + '...'
  }

  return {
    renderMarkdown,
    stripMarkdown,
    normalizeNewlines: normalizeMarkdownNewlines,
    getExcerpt,
    markdownIt: md
  }
}
