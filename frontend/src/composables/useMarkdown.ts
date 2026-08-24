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

/** useMarkdown 返回的渲染工具集 */
export interface MarkdownUtils {
  /** Render markdown string to HTML */
  renderMarkdown: (content: string) => string
  /** Strip markdown formatting and return plain text */
  stripMarkdown: (content: string) => string
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
    return md.render(content)
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
    getExcerpt,
    markdownIt: md
  }
}
