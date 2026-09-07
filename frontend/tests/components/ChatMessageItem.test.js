import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('@/stores/toast', () => ({
  useToastStore: () => ({
    show: vi.fn(),
    error: vi.fn(),
    success: vi.fn(),
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

    // 来源点击触发 scrollToSource
    const sourceBtn = wrapper.find('.source-row')
    await sourceBtn.trigger('click')
    expect(wrapper.emitted('scrollToSource')).toBeTruthy()
    expect(wrapper.emitted('scrollToSource')?.[0][0]).toBe(1)
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
    expect(wrapper.text()).toContain('正在推理中...')

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
})

