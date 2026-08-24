import { describe, it, expect } from 'vitest'

import { buildChatMarkdown } from '@/composables/useChatExport'

describe('buildChatMarkdown', () => {
  const messages = [
    { role: 'user', content: '什么是 FAISS？' },
    {
      role: 'assistant',
      content: 'FAISS 是向量检索库。',
      sources: [
        { source: '讲义.pdf', page: '3', text: 'FAISS 简介' },
        { source: '', page: '', text: '' },
      ],
    },
  ]

  it('标题缺省回退为「对话」', () => {
    const md = buildChatMarkdown(messages, '')
    expect(md.startsWith('# 对话')).toBe(true)
  })

  it('按 用户/AI 分节渲染内容与来源清单', () => {
    const md = buildChatMarkdown(messages, '向量检索问答')
    expect(md).toContain('# 向量检索问答')
    expect(md).toContain('## 用户\n\n什么是 FAISS？')
    expect(md).toContain('## AI\n\nFAISS 是向量检索库。')
    expect(md).toContain('## 参考来源')
    expect(md).toMatch(/1\. 讲义\.pdf P3 — FAISS 简介/)
    // 空字段不应产生多余的页码/文本尾巴
    expect(md).toMatch(/2\. 未知来源\n/)
  })

  it('无来源的助手消息不输出参考来源小节', () => {
    const md = buildChatMarkdown([{ role: 'assistant', content: 'ok' }], 't')
    expect(md).not.toContain('## 参考来源')
  })
})
