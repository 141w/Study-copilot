/**
 * 回归测试：SSE error 事件必须写入消息气泡（修复：此前被静默丢弃，
 * 用户只看到空白回答停止加载，LLM 故障完全不可见）。
 *
 * 后端契约：LLM 失败时流内发出
 *   data: {"type": "error", "message": "AI 服务余额不足..."}
 *   data: {"type": "done"}
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/services/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
  cancelAll: vi.fn(),
  refreshAccessToken: vi.fn(),
}))

import { setActivePinia, createPinia } from 'pinia'
import { useChatStore } from '@/stores/chat'

/** 把事件序列编码为 SSE 字节流 */
function sseStream(events) {
  const enc = new TextEncoder()
  const payload = events
    .map((e) => 'data: ' + JSON.stringify(e) + '\n')
    .join('\n')
  return new ReadableStream({
    start(controller) {
      controller.enqueue(enc.encode(payload))
      controller.close()
    },
  })
}

describe('Chat Store — SSE error 事件可见性', () => {
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useChatStore()
    localStorage.clear()
    localStorage.setItem('token', 'test-token')
  })

  it('error 事件把 message 写入助手消息并停止流式', async () => {
    const mockResponse = {
      ok: true,
      status: 200,
      body: sseStream([
        { type: 'session', session_id: 'sess-1' },
        { type: 'sources', sources: [], filtered_sources: [] },
        {
          type: 'error',
          message: 'AI 服务余额不足或计费异常，请检查账户额度或更换模型提供商。',
        },
        { type: 'done' },
      ]),
    }
    global.fetch = vi.fn().mockResolvedValue(mockResponse)

    await store.askQuestionStream('光合作用的场所？', ['doc-1'])

    const aiMsg = store.messages.find((m) => m.role === 'assistant')
    expect(aiMsg).toBeDefined()
    expect(aiMsg.isStreaming).toBe(false)
    expect(aiMsg.content).toContain('余额不足')
  })

  it('error 事件不覆盖已流式输出的部分内容（追加而非替换）', async () => {
    const mockResponse = {
      ok: true,
      status: 200,
      body: sseStream([
        { type: 'session', session_id: 'sess-2' },
        { type: 'token', content: '光合作用发生在' },
        {
          type: 'error',
          message: 'AI 服务暂时不可用，请稍后重试。',
        },
        { type: 'done' },
      ]),
    }
    global.fetch = vi.fn().mockResolvedValue(mockResponse)

    await store.askQuestionStream('继续说', ['doc-1'])

    const aiMsg = store.messages.find((m) => m.role === 'assistant')
    expect(aiMsg.content).toContain('光合作用发生在')
    expect(aiMsg.content).toContain('AI 服务暂时不可用')
  })

  it('无 message 的 error 事件使用兜底文案', async () => {
    const mockResponse = {
      ok: true,
      status: 200,
      body: sseStream([{ type: 'error' }, { type: 'done' }]),
    }
    global.fetch = vi.fn().mockResolvedValue(mockResponse)

    await store.askQuestionStream('测试', ['doc-1'])

    const aiMsg = store.messages.find((m) => m.role === 'assistant')
    expect(aiMsg.content).toBe('回答生成失败，请稍后重试')
  })
})
