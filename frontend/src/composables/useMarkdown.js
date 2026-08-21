import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'

// Create markdown-it instance with highlight.js
const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  highlight: function (str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return '<pre class="hljs"><code>' +
               hljs.highlight(str, { language: lang, ignoreIllegals: true }).value +
               '</code></pre>'
      } catch (__) {}
    }
    // Unknown/failed language: escaped plain-text code block
    return '<pre class="hljs"><code>' + md.utils.escapeHtml(str) + '</code></pre>'
  }
})

/**
 * Composable for Markdown rendering
 * @returns {Object} Markdown rendering utilities
 */
export function useMarkdown() {
  /**
   * Render markdown string to HTML
   * @param {string} content - Markdown content
   * @returns {string} Rendered HTML
   */
  function renderMarkdown(content) {
    if (!content) return ''
    return md.render(content)
  }

  /**
   * Strip markdown formatting and return plain text
   * @param {string} content - Markdown content
   * @returns {string} Plain text
   */
  function stripMarkdown(content) {
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
   * @param {string} content - Markdown content
   * @param {number} length - Max length
   * @returns {string} Truncated plain text
   */
  function getExcerpt(content, length = 150) {
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
