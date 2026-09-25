import { describe, it, expect } from 'vitest'
import {
  hideIncompleteCitationTail,
  swapCitationsForPlaceholders,
  restoreCitationPlaceholders,
  prepareCitationMarkdown,
  finalizeCitationHtml,
  makeCitationBadge,
  CITATION_BADGE_CLASS,
} from '@/utils/citationMarkdown'

describe('citationMarkdown — 引用标记占位符管线', () => {
  it('解析前把 [来源N] 换成占位符，解析后还原为角标 HTML', () => {
    const md = '梯度下降是优化算法 [来源1]，也可参考 [来源12]。'
    const prepared = swapCitationsForPlaceholders(md)

    // 占位符里不再出现会被 markdown 误解析的 [来源N] 字面量
    expect(prepared).not.toContain('[来源1]')
    expect(prepared).not.toContain('[来源12]')

    // 模拟 markdown-it：html:false 时占位符原样穿过（作为纯文本）
    const rendered = `<p>${prepared}</p>`
    const html = restoreCitationPlaceholders(rendered)

    expect(html).toContain('class="source-badge"')
    expect(html).toContain('data-index="1"')
    expect(html).toContain('data-index="12"')
    expect(html).toContain('>[1]<')
    expect(html).toContain('>[12]<')
    // 不再残留占位符私有区字符
    expect(html).not.toContain('\uE000')
    expect(html).not.toContain('\uE001')
  })

  it('占位符在含 markdown 强调/链接语法的上下文中不被破坏', () => {
    const md = '**重点** [来源2] 以及 [链接](https://example.com)'
    const prepared = swapCitationsForPlaceholders(md)
    // 强调与真实链接保留
    expect(prepared).toContain('**重点**')
    expect(prepared).toContain('[链接](https://example.com)')
    // 引用标记换成占位符，避免被当成又一个链接标签
    expect(prepared).not.toContain('[来源2]')

    const html = finalizeCitationHtml(`<p>${prepared}</p>`)
    expect(html).toContain('data-index="2"')
  })

  it('流式尾部隐藏残缺的 [来源… 标记', () => {
    expect(hideIncompleteCitationTail('答案 [来源', true)).toBe('答案 ')
    expect(hideIncompleteCitationTail('答案 [来源1', true)).toBe('答案 ')
    expect(hideIncompleteCitationTail('答案 [来源12', true)).toBe('答案 ')
    expect(hideIncompleteCitationTail('答案 [来源1]', true)).toBe('答案 [来源1]')
    // 已闭合的标记不动，后文继续
    expect(hideIncompleteCitationTail('答案 [来源3] 继续', true)).toBe('答案 [来源3] 继续')
  })

  it('非流式不隐藏看似残缺的尾部（完成态原样保留/由后续兜底还原）', () => {
    expect(hideIncompleteCitationTail('答案 [来源', false)).toBe('答案 [来源')
    expect(hideIncompleteCitationTail('答案 [来源1', false)).toBe('答案 [来源1')
  })

  it('prepareCitationMarkdown：流式先隐藏残缺再换占位符', () => {
    const out = prepareCitationMarkdown('论点 [来源1] 补充 [来源', true)
    expect(out).not.toContain('[来源1]')
    expect(out).not.toContain('[来源')
    const html = finalizeCitationHtml(`<p>${out}</p>`)
    expect(html).toContain('data-index="1"')
    // 残缺标记不会变成角标
    expect(html.match(/source-badge/g)?.length).toBe(1)
  })

  it('restoreCitationPlaceholders 兜底还原 HTML 中残留的字面 [来源N]', () => {
    // 历史缓存 / 外部拼接：可能仍是字面 [来源4]
    const html = restoreCitationPlaceholders('<p>见 [来源4]</p>')
    expect(html).toContain(makeCitationBadge(4))
    expect(html).toContain(`class="${CITATION_BADGE_CLASS}"`)
    expect(html).not.toContain('[来源4]')
  })

  it('makeCitationBadge 输出与既有 .source-badge 契约一致', () => {
    const badge = makeCitationBadge(7)
    expect(badge).toBe('<sup class="source-badge" data-index="7">[7]</sup>')
  })

  it('无引用文本的管线空转（空串 / 纯文本）', () => {
    expect(prepareCitationMarkdown('', true)).toBe('')
    expect(finalizeCitationHtml('')).toBe('')
    expect(prepareCitationMarkdown('普通句子。', false)).toBe('普通句子。')
    expect(finalizeCitationHtml('<p>普通句子。</p>')).toBe('<p>普通句子。</p>')
  })
})
