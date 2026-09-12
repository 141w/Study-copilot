import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('@/stores/toast', () => ({
  useToastStore: () => ({
    show: vi.fn(),
    error: vi.fn(),
    success: vi.fn(),
  }),
}))

const mockPush = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
  useRoute: () => ({
    query: {},
  }),
}))

vi.mock('@/components/TTSPlayer.vue', () => ({
  default: {
    name: 'TTSPlayer',
    template: '<div data-test="tts-player"></div>',
    props: ['text']
  }
}))

import ChatMessageItem from '@/components/chat/ChatMessageItem.vue'
import ChatDiscussionItem from '@/components/chat/ChatDiscussionItem.vue'

describe('ChatMessageItem & ChatDiscussionItem', () => {
  it('正确渲染用户角色消息并规范化裸露换行符', () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        message: {
          id: '1',
          role: 'user',
          content: '请解释什么是 RAG？\\n第二行提问',
          created_at: new Date().toISOString()
        }
      }
    })
    expect(wrapper.text()).toContain('请解释什么是 RAG？\n第二行提问')
    expect(wrapper.text()).not.toContain('\\n')
    expect(wrapper.find('.msg-enter').exists()).toBe(true)
  })

  it('正确渲染 Assistant 消息、思考步骤与来源', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        message: {
          id: '2',
          role: 'assistant',
          content: 'RAG 即检索增强生成。',
          thinking: [
            { step: 1, detail: '检索知识库' },
            { step: 2, detail: '生成回答' }
          ],
          sources: [
            { index: 1, source: 'rag_paper.pdf', page: 3, text: 'RAG 架构解析' }
          ],
          used_source_indices: [1],
          created_at: new Date().toISOString()
        },
        renderedMarkdown: '<p>RAG 即检索增强生成。</p>',
        showAvatar: true,
        isLatestAssistant: true
      },
      global: {
        stubs: {
          CopilotBotAvatar: { template: '<div data-test="bot-avatar"></div>' },
          TTSPlayer: { template: '<div data-test="tts-player"></div>' },
          'el-icon': true,
          'el-button': {
            template: '<button data-test="btn" @click="$emit(\'click\')"><slot /></button>',
            emits: ['click']
          }
        }
      }
    })

    expect(wrapper.text()).toContain('Study Copilot')
    expect(wrapper.text()).toContain('思考过程 (2 步)')
    expect(wrapper.text()).toContain('检索知识库')
    expect(wrapper.html()).toContain('RAG 即检索增强生成。')
    expect(wrapper.text()).toContain('rag_paper.pdf')
    expect(wrapper.text()).toContain('P3')
    expect(wrapper.find('.sticky').exists()).toBe(true)

    // 复制按钮测试
    const copyBtn = wrapper.find('[data-test="btn"]')
    await copyBtn.trigger('click')
    expect(wrapper.emitted('copy')).toBeTruthy()
    expect(wrapper.emitted('copy')?.[0][0].id).toBe('2')

    // 来源卡可见：默认只显示标题，正文摘要需点击展开
    expect(wrapper.find('.source-card').exists()).toBe(true)
    expect(wrapper.text()).toContain('rag_paper.pdf')
    expect(wrapper.text()).not.toContain('RAG 架构解析')
    const cardToggle = wrapper.find('[data-test="source-card-toggle-1"]')
    expect(cardToggle.exists()).toBe(true)
    expect(cardToggle.attributes('aria-expanded')).toBe('false')
    await cardToggle.trigger('click')
    expect(cardToggle.attributes('aria-expanded')).toBe('true')
    expect(wrapper.text()).toContain('RAG 架构解析')
  })

  it('深度研究：正文未出仅来源摘要行，完整卡延迟到首 token 后', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        message: {
          id: 'deep-1',
          role: 'assistant',
          content: '',
          thinking: [
            { step: 'agent_start', detail: '启动深度研究' },
            { step: 'tool_call', detail: '调用 knowledge_search' },
            { step: 'tool_result', detail: '累计 1 条来源' },
          ],
          reasoning: '启动深度研究\n调用 knowledge_search\n累计 1 条来源\n',
          sources: [
            { index: 1, source: 'ml_notes.md', page: '1', text: '梯度下降是一种优化算法', document_id: 'd1' },
          ],
          filtered_sources: [
            { index: 1, source: 'ml_notes.md', page: '1', text: '梯度下降是一种优化算法', document_id: 'd1' },
          ],
          isStreaming: true,
          created_at: new Date().toISOString(),
        },
        renderedMarkdown: '',
        renderedReasoning: '<p>证据链</p>',
      },
      global: {
        stubs: {
          CopilotBotAvatar: true,
          TTSPlayer: true,
          'el-icon': true,
          'el-button': true,
        },
      },
    })

    await wrapper.vm.$nextTick()

    // 研究阶段：来源区有，但只有摘要行，不铺完整卡
    expect(wrapper.find('[data-test="sources-section"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="sources-research-hint"]').exists()).toBe(true)
    expect(wrapper.find('.source-card').exists()).toBe(false)
    expect(wrapper.text()).toContain('研究中，已定位 1 个来源')
    expect(wrapper.text()).not.toContain('梯度下降是一种优化算法')
    // Agent 徽章 + 双轨面板（与快速模式一致：默认折叠，不强制展开）
    expect(wrapper.text()).toContain('研究启动')
    expect(wrapper.find('.thinking-section').exists()).toBe(true)
    expect(wrapper.find('.reasoning-box').exists()).toBe(true)
    // 折叠态：details 不带 open
    expect(wrapper.find('.thinking-section').attributes('open')).toBeUndefined()
  })

  it('来源卡：首 token 后展示完整卡且默认展开，可折叠切换', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        message: {
          id: 'deep-2',
          role: 'assistant',
          content: '',
          sources: [
            { index: 1, source: 'ml_notes.md', page: '1', text: '梯度下降是一种优化算法', document_id: 'd1' },
          ],
          filtered_sources: [
            { index: 1, source: 'ml_notes.md', page: '1', text: '梯度下降是一种优化算法', document_id: 'd1' },
          ],
          isStreaming: true,
          created_at: new Date().toISOString(),
        },
      },
      global: {
        stubs: {
          CopilotBotAvatar: true,
          TTSPlayer: true,
          'el-icon': true,
          'el-button': true,
        },
      },
    })

    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-test="sources-research-hint"]').exists()).toBe(true)
    expect(wrapper.find('.source-card').exists()).toBe(false)

    // 首 token 到达
    await wrapper.setProps({
      message: {
        id: 'deep-2',
        role: 'assistant',
        content: '梯度下降是优化算法 [来源1]',
        sources: [
          { index: 1, source: 'ml_notes.md', page: '1', text: '梯度下降是一种优化算法', document_id: 'd1' },
        ],
        filtered_sources: [
          { index: 1, source: 'ml_notes.md', page: '1', text: '梯度下降是一种优化算法', document_id: 'd1' },
        ],
        isStreaming: true,
        created_at: new Date().toISOString(),
      },
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-test="sources-research-hint"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="sources-toggle"]').exists()).toBe(true)
    expect(wrapper.find('.source-card').exists()).toBe(true)
    expect(wrapper.text()).toContain('ml_notes.md')
    // 卡内正文默认折叠，仅标题
    expect(wrapper.text()).not.toContain('梯度下降是一种优化算法')
    expect(wrapper.find('[data-test="source-card-body"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="sources-toggle"]').attributes('aria-expanded')).toBe('true')

    // 展开单卡详情
    await wrapper.find('[data-test="source-card-toggle-1"]').trigger('click')
    expect(wrapper.text()).toContain('梯度下降是一种优化算法')
    expect(wrapper.find('[data-test="source-card-body"]').exists()).toBe(true)

    // 收起外层来源区
    await wrapper.find('[data-test="sources-toggle"]').trigger('click')
    expect(wrapper.find('[data-test="sources-toggle"]').attributes('aria-expanded')).toBe('false')
    expect(wrapper.find('.source-card').exists()).toBe(false)
    expect(wrapper.text()).toContain('参考来源')

    // 再展开
    await wrapper.find('[data-test="sources-toggle"]').trigger('click')
    expect(wrapper.find('[data-test="sources-toggle"]').attributes('aria-expanded')).toBe('true')
    expect(wrapper.find('.source-card').exists()).toBe(true)
  })

  it('历史消息（非流式）来源区默认展开，单卡默认只显示标题', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        message: {
          id: 'hist-1',
          role: 'assistant',
          content: '回答内容 [来源1]',
          sources: [
            { index: 1, source: 'notes.md', page: '2', text: '原文摘要', document_id: 'd1' },
          ],
          isStreaming: false,
          created_at: new Date().toISOString(),
        },
      },
      global: {
        stubs: {
          CopilotBotAvatar: true,
          TTSPlayer: true,
          'el-icon': true,
          'el-button': true,
        },
      },
    })
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.source-card').exists()).toBe(true)
    expect(wrapper.find('[data-test="sources-toggle"]').attributes('aria-expanded')).toBe('true')
    // 单卡正文默认折叠
    expect(wrapper.text()).toContain('notes.md')
    expect(wrapper.text()).not.toContain('原文摘要')
    await wrapper.find('[data-test="source-card-toggle-1"]').trigger('click')
    expect(wrapper.text()).toContain('原文摘要')
  })

  it('正确渲染原生 CoT 深度思考面板（Reasoning Box）与折叠交互', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        message: {
          id: 'cot-1',
          role: 'assistant',
          content: '最终输出回答内容。',
          reasoning: '首先分析题目已知条件，假设输入空间为欧氏空间...',
          thinking: [
            { step: 'intent_analysis', detail: '意图识别：文档问答' }
          ],
          isStreaming: false,
          created_at: new Date().toISOString()
        },
        renderedMarkdown: '<p>最终输出回答内容。</p>',
        renderedReasoning: '<p>首先分析题目已知条件，假设输入空间为欧氏空间...</p>'
      },
      global: {
        stubs: {
          CopilotBotAvatar: true,
          TTSPlayer: true,
          'el-icon': true,
          'el-button': true
        }
      }
    })

    // 思考结束后：单行展示标题，不需要展示思考缩略内容
    expect(wrapper.text()).toContain('已完成深度思考')
    expect(wrapper.text()).toContain('Agentic 思考过程 (1 步)')
    expect(wrapper.text()).not.toContain('· 首先分析题目已知条件')
    expect(wrapper.text()).not.toContain('· 意图拆解')

    // 两个思考过程右侧均不显示展开/收起按钮文本
    const thinkingSummary = wrapper.find('.thinking-summary')
    const reasoningSummary = wrapper.find('.reasoning-summary')
    expect(thinkingSummary.text()).not.toContain('展开')
    expect(thinkingSummary.text()).not.toContain('收起')
    expect(reasoningSummary.text()).not.toContain('展开')
    expect(reasoningSummary.text()).not.toContain('收起')

    // 点击切换折叠展开
    await reasoningSummary.trigger('click')
    expect(wrapper.find('.reasoning-box').attributes('open')).toBeDefined()
  })

  it('思考过程中为双行，思考完成正文开始吐字时自动收起为单行且不展示缩略内容', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        message: {
          id: 'stream-1',
          role: 'assistant',
          content: '',
          reasoning: '正在推理中...',
          thinking: [
            { step: 'adaptive_retrieve', detail: '检索到 3 个切片' }
          ],
          isStreaming: true,
          created_at: new Date().toISOString()
        }
      },
      global: {
        stubs: {
          CopilotBotAvatar: true,
          TTSPlayer: true,
          'el-icon': true,
          'el-button': true
        }
      }
    })

    // 思考过程中：展示第二行动态片段（双行）
    expect(wrapper.text()).toContain('正在深度思考...')
    // reasoning 正文（展开或缩略均可出现原文/截断）
    expect(wrapper.find('.reasoning-box').exists()).toBe(true)

    // 思考完成，正式回答正文开始到达
    await wrapper.setProps({
      message: {
        id: 'stream-1',
        role: 'assistant',
        content: '这是正式回答的第一句',
        reasoning: '正在推理中...',
        thinking: [
          { step: 'adaptive_retrieve', detail: '检索到 3 个切片' }
        ],
        isStreaming: true,
        created_at: new Date().toISOString()
      }
    })

    // 验证：自动收缩为折叠单行，且不需要展示思考缩略内容
    expect(wrapper.find('.reasoning-box').attributes('open')).toBeUndefined()
    expect(wrapper.find('.thinking-section').attributes('open')).toBeUndefined()
    expect(wrapper.text()).toContain('已完成深度思考')
    expect(wrapper.text()).toContain('Agentic 思考过程 (1 步)')
    expect(wrapper.text()).not.toContain('· 知识检索')
  })

  it('正确渲染多角色讨论 ChatDiscussionItem', () => {
    const wrapper = mount(ChatDiscussionItem, {
      props: {
        message: {
          id: 'disc-1',
          role: 'discussion',
          content: '',
          personas: [
            { name: '学者 A', avatar: '👨‍🏫', content: '我认为重点在于检索召回率。' },
            { name: '工程师 B', avatar: '👩‍💻', content: '我更看重端到端延迟与重排性能。' }
          ],
          isStreaming: true,
          created_at: new Date().toISOString()
        }
      }
    })

    expect(wrapper.text()).toContain('多角色讨论')
    expect(wrapper.text()).toContain('学者 A')
    expect(wrapper.text()).toContain('我认为重点在于检索召回率。')
    expect(wrapper.text()).toContain('工程师 B')
    expect(wrapper.text()).toContain('我更看重端到端延迟与重排性能。')
    expect(wrapper.text()).toContain('讨论中…')
  })

  it('ChatDiscussionItem 渲染错误提示', () => {
    const wrapper = mount(ChatDiscussionItem, {
      props: {
        message: {
          id: 'disc-err',
          role: 'discussion',
          content: '讨论服务暂时不可用：The model does not exist',
          error: '讨论服务暂时不可用：The model does not exist',
          personas: [],
          isStreaming: false,
          created_at: new Date().toISOString()
        }
      }
    })

    expect(wrapper.text()).toContain('多角色讨论')
    expect(wrapper.text()).toContain('讨论服务暂时不可用：The model does not exist')
    expect(wrapper.text()).not.toContain('讨论中…')
  })

  it('ChatDiscussionItem 渲染主持人讨论总结卡片', () => {
    const wrapper = mount(ChatDiscussionItem, {
      props: {
        message: {
          id: 'disc-summary',
          role: 'discussion',
          content: '【苏老师】：你好\n\n---\n\n**讨论总结**\n\n本次讨论达成一致，推荐使用分层检索。',
          summary: '本次讨论达成一致，推荐使用分层检索。',
          personas: [
            { name: '苏老师', avatar: 'User', content: '你好' }
          ],
          isStreaming: false,
          created_at: new Date().toISOString()
        }
      }
    })

    expect(wrapper.text()).toContain('多角色讨论')
    expect(wrapper.text()).toContain('苏老师')
    expect(wrapper.text()).toContain('讨论总结')
    expect(wrapper.text()).toContain('本次讨论达成一致，推荐使用分层检索。')
  })

  it('ChatDiscussionItem 渲染筹备等待态', () => {
    const wrapper = mount(ChatDiscussionItem, {
      props: {
        message: {
          id: 'disc-prep',
          role: 'discussion',
          content: '',
          personas: [],
          isStreaming: true,
          created_at: new Date().toISOString()
        }
      }
    })

    expect(wrapper.text()).toContain('研讨角色正在梳理思路，准备发言…')
  })

  it('ChatDiscussionItem 渲染时序交锋流与当前活跃发言者', () => {
    const wrapper = mount(ChatDiscussionItem, {
      props: {
        message: {
          id: 'disc-timeline',
          role: 'discussion',
          content: '【学霸】：观点一\n\n【求知同学】：追问二',
          discussionTurns: [
            {
              id: 't-1',
              persona: '学霸',
              avatar: 'GraduationCap',
              color: '#10b981',
              content: '我认为向量空间是基础。',
              turn: 1,
              isStreaming: false
            },
            {
              id: 't-2',
              persona: '求知同学',
              avatar: 'ChatLineRound',
              color: '#f59e0b',
              content: '如果维数无限呢？',
              turn: 1,
              isStreaming: true
            }
          ],
          currentSpeaker: {
            name: '求知同学',
            avatar: 'ChatLineRound',
            color: '#f59e0b',
            action: '正在针对前序观点进行深度互辩…'
          },
          isStreaming: true,
          created_at: new Date().toISOString()
        }
      }
    })

    expect(wrapper.text()).toContain('多角色讨论')
    expect(wrapper.text()).toContain('2 轮观点交锋')
    expect(wrapper.text()).toContain('求知同学')
    expect(wrapper.text()).toContain('正在针对前序观点进行深度互辩…')
    expect(wrapper.text()).toContain('我认为向量空间是基础。')
    expect(wrapper.text()).toContain('如果维数无限呢？')
    expect(wrapper.text()).toContain('发言中…')
  })

  it('ChatDiscussionItem 支持一级菜单与二级轮次菜单折叠与展开', async () => {
    const wrapper = mount(ChatDiscussionItem, {
      props: {
        message: {
          id: 'disc-multi-round',
          role: 'discussion',
          content: '【学霸】：第一轮\n\n【学霸】：第二轮',
          discussionTurns: [
            {
              id: 't-r1-1',
              persona: '学霸',
              avatar: 'GraduationCap',
              color: '#10b981',
              content: '第一轮论点：基础机制。',
              turn: 1,
              isStreaming: false
            },
            {
              id: 't-r2-1',
              persona: '学霸',
              avatar: 'GraduationCap',
              color: '#10b981',
              content: '第二轮论点：边界与陷阱。',
              turn: 2,
              isStreaming: false
            }
          ],
          summary: '两轮讨论核心共识总结',
          isStreaming: false,
          created_at: new Date().toISOString()
        }
      }
    })

    // 验证一级菜单标题与轮次统计
    expect(wrapper.text()).toContain('多角色研讨过程')
    expect(wrapper.text()).toContain('共 2 轮交锋')
    expect(wrapper.text()).toContain('第 1 轮 · 初始立论与破题')
    expect(wrapper.text()).toContain('第 2 轮 · 深度互辩与交锋')
    expect(wrapper.text()).toContain('第一轮论点：基础机制。')
    expect(wrapper.text()).toContain('第二轮论点：边界与陷阱。')

    // 点击一级菜单顶栏折叠
    const collapseHeader = wrapper.find('.cursor-pointer')
    expect(collapseHeader.exists()).toBe(true)
    await collapseHeader.trigger('click')

    // 即使折叠了一级讨论过程，主持人总结依然醒目可见
    expect(wrapper.text()).toContain('讨论总结')
    expect(wrapper.text()).toContain('两轮讨论核心共识总结')
  })

  it('ChatDiscussionItem 支持三级角色单条发言正文的折叠与展开', async () => {
    const wrapper = mount(ChatDiscussionItem, {
      props: {
        message: {
          id: 'disc-turn-collapse',
          role: 'discussion',
          content: '【学霸】：这是详尽的论述正文。',
          discussionTurns: [
            {
              id: 't-collapse-1',
              persona: '学霸',
              avatar: 'GraduationCap',
              color: '#10b981',
              content: '这是详尽的论述正文。',
              turn: 1,
              isStreaming: false
            }
          ],
          summary: '结论',
          isStreaming: false,
          created_at: new Date().toISOString()
        }
      }
    })

    // 初始状态：三级发言默认展开，显示正文与“收起”操作
    expect(wrapper.text()).toContain('这是详尽的论述正文。')
    expect(wrapper.text()).toContain('收起')

    // 查找三级发言卡片的折叠顶栏并触发点击
    const turnHeaders = wrapper.findAll('.cursor-pointer')
    // turnHeaders[0] 是一级研讨容器, turnHeaders[1] 是二级轮次面板, turnHeaders[2] 是三级发言卡片顶栏
    const turnCardHeader = turnHeaders[2]
    expect(turnCardHeader).toBeDefined()
    await turnCardHeader.trigger('click')

    // 折叠后：显示“展开”，且包含单行文本缩略预览
    expect(wrapper.text()).toContain('展开')
    expect(wrapper.text()).toContain('这是详尽的论述正文。')

    // 再次点击：展开恢复“收起”
    await turnCardHeader.trigger('click')
    expect(wrapper.text()).toContain('收起')
  })

  it('正确渲染已保存至笔记卡片与标签', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        message: {
          id: 'note-msg-1',
          role: 'assistant',
          content: '这是一份整理好的笔记正文',
          savedNote: {
            id: 'note-999',
            title: 'Transformer 架构详解笔记',
            tags: ['AI', '架构', 'Transformer']
          },
          created_at: new Date().toISOString()
        }
      },
      global: {
        stubs: {
          CopilotBotAvatar: true,
          TTSPlayer: true,
          'el-icon': true,
          'el-button': {
            template: '<button class="test-btn" @click="$emit(\'click\')"><slot /></button>',
            emits: ['click']
          }
        }
      }
    })

    expect(wrapper.find('.saved-note-card').exists()).toBe(true)
    expect(wrapper.text()).toContain('Transformer 架构详解笔记')
    expect(wrapper.text()).toContain('已存入笔记')
    expect(wrapper.text()).toContain('#Transformer')
    expect(wrapper.text()).toContain('查看笔记')
    expect(wrapper.text()).toContain('已存笔记')

    const viewNoteBtn = wrapper.find('.saved-note-card .test-btn')
    await viewNoteBtn.trigger('click')
    expect(mockPush).toHaveBeenCalledWith({ path: '/notes', query: { id: 'note-999' } })
  })

  it('在无 savedNote 时渲染“存为笔记”按钮并触发保存', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        message: {
          id: 'msg-to-save',
          role: 'assistant',
          content: '可被提炼为笔记的内容',
          created_at: new Date().toISOString()
        }
      },
      global: {
        stubs: {
          CopilotBotAvatar: true,
          TTSPlayer: true,
          'el-icon': true,
          'el-button': {
            template: '<button class="test-btn" @click="$emit(\'click\')"><slot /></button>',
            emits: ['click']
          }
        }
      }
    })

    expect(wrapper.text()).toContain('存为笔记')
    const buttons = wrapper.findAll('.test-btn')
    const saveBtn = buttons.find(b => b.text().includes('存为笔记'))
    expect(saveBtn).toBeDefined()
    await saveBtn.trigger('click')
    expect(wrapper.emitted('saveNote')).toBeTruthy()
    expect(wrapper.emitted('saveNote')?.[0][0].id).toBe('msg-to-save')
  })

  it('点击正文角标 .source-badge 触发 scrollToSource 事件并自动展开来源面板', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        message: {
          id: 'msg-badge-click',
          role: 'assistant',
          content: '知识检索结果详见 <sup class="source-badge" data-index="1">[1]</sup> 章节。',
          sources: [
            { index: 1, source: 'ai_guide.pdf', page: '42', text: 'AI 引导概述正文', document_id: 'd-1' }
          ],
          isStreaming: false,
          created_at: new Date().toISOString()
        },
        renderedMarkdown: '知识检索结果详见 <sup class="source-badge" data-index="1">[1]</sup> 章节。'
      },
      global: {
        stubs: {
          CopilotBotAvatar: true,
          TTSPlayer: true,
          'el-icon': true,
          'el-button': true
        }
      }
    })

    const badge = wrapper.find('.source-badge')
    expect(badge.exists()).toBe(true)
    await badge.trigger('click')

    expect(wrapper.emitted('scrollToSource')).toBeTruthy()
    expect(wrapper.emitted('scrollToSource')?.[0][0]).toBe(1)
    expect(wrapper.find('[data-test="sources-toggle"]').attributes('aria-expanded')).toBe('true')
  })

  it('来源卡片 ChatSourceCards 具有暗色模式适配类名与正文摘录强调结构', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        message: {
          id: 'msg-dark-sources',
          role: 'assistant',
          content: '正文',
          sources: [
            { index: 2, source: 'system_design.docx', page: '8', text: '系统设计正文摘录', document_id: 'd-2' }
          ],
          isStreaming: false,
          created_at: new Date().toISOString()
        }
      },
      global: {
        stubs: {
          CopilotBotAvatar: true,
          TTSPlayer: true,
          'el-icon': true,
          'el-button': true
        }
      }
    })

    const card = wrapper.find('.source-card')
    expect(card.exists()).toBe(true)
    // 重构后来源卡样式走 scoped 语义类；触发按钮必须带「剥 UA 原生皮肤」的专用类
    // （项目未启用 Tailwind preflight，裸 button 会带 ButtonFace 灰底 + outset 浮雕框）
    expect(card.find('button').classes()).toContain('source-card__trigger')

    // 展开卡片
    const toggleBtn = wrapper.find('[data-test="source-card-toggle-2"]')
    await toggleBtn.trigger('click')

    expect(toggleBtn.attributes('aria-expanded')).toBe('true')
    expect(card.classes()).toContain('source-card--open')
    const body = wrapper.find('[data-test="source-card-body"]')
    expect(body.exists()).toBe(true)
    expect(body.classes()).toContain('source-card__body')
    expect(body.find('button').classes()).toContain('source-card__copy')
    expect(wrapper.text()).toContain('系统设计正文摘录')
  })
})

