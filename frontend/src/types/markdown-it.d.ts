/**
 * 本地最小 ambient 声明：markdown-it@14 未内置类型，项目未安装 @types/markdown-it。
 * 仅覆盖本仓库实际使用的 API 面（构造选项 / render / parse / utils.escapeHtml）。
 * 若后续安装官方 @types/markdown-it，可删除此文件。
 */
declare module 'markdown-it' {
  export interface MarkdownItOptions {
    /** HTML 标签直出开关 */
    html?: boolean
    xhtmlOut?: boolean
    breaks?: boolean
    langPrefix?: string
    linkify?: boolean
    typographer?: boolean
    quotes?: string | string[]
    highlight?: (str: string, lang: string, attrs: string) => string
  }

  export class MarkdownIt {
    constructor(options?: MarkdownItOptions)
    render(src: string, env?: unknown): string
    parse(src: string, env?: unknown): unknown[]
    utils: {
      escapeHtml(str: string): string
    }
  }

  export default MarkdownIt
}
