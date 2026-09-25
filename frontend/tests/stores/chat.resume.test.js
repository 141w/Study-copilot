/**
 * 5.5 断线续流 + 5.4 停止语义（AbortError 保留部分回答）。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/services/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
  cancelAll: vi.fn(),
}))

import { setActivePinia, createPinia } from 'pinia'
import { useChatStore } from '@/stores/chat'
import api from '@/services/api'

function sseStream(events) {
  const enc = new TextEncoder()
  const payload = events.map((e) => 'data: ' + JSON.stringify(e) + '\n').join('\n')
  return new ReadableStream({
    start(controller) {
      controller.enqueue(enc.encode(payload))
      controller.close()
    },
  })
}

describe('Chat Store — 断线续流 / 停止保留部分回答', () => {
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useChatStore()
    vi.clearAllMocks()
    localStorage.clear()
    localStorage.setItem('token', 'test-token')
  })

  it('AbortError 保留部分回答并标记 incomplete（5.4）', async () => {
    const enc = new TextEncoder()
    let aborted = false
    global.fetch = vi.fn().mockImplementation((_url, opts) => {
      return new Promise((_resolve, reject) => {
        opts.signal.addEventListener('abort', () => {
          aborted = true
          const err = new Error('The operation was aborted.')
          err.name = 'AbortError'
          reject(err)
        })
        // 模拟已流出部分 token 后被用户停止
        queueMicrotask(() => {
          // apply partial via side channel: askQuestionStream will not get these
          // because we abort before resolve — so pre-seed after start is not possible.
          // Instead resolve a stream that yields one token then waits for abort.
        })
      })
    })
    // 更直接：用可控 reader 流，发一个 token 后挂起，再 abort
    global.fetch = vi.fn().mockImplementation((_url, opts) => {
      const stream = new ReadableStream({
        start(controller) {
          controller.enqueue(enc.encode('data: ' + JSON.stringify({ type: 'token', content: '部分' }) + '\n\n'))
          opts.signal.addEventListener('abort', () => {
            const err = new Error('aborted')
            err.name = 'AbortError'
            try { controller.error(err) } catch { /* closed */ }
          })
        },
      })
      return Promise.resolve({ ok: true, status: 200, body: stream })
    })

    const p = store.askQuestionStream('问题', [])
    // 等 token 写入后取消
    await new Promise((r) => setTimeout(r, 10))
    store.cancelStream()
    const result = await p

    expect(result.cancelled).toBe(true)
    const aiMsg = store.messages.find((m) => m.role === 'assistant')
    expect(aiMsg).toBeTruthy()
    expect(aiMsg.content).toContain('部分')
    expect(aiMsg.isStreaming).toBe(false)
    expect(aborted || aiMsg.incomplete === true).toBeTruthy()
  })

  it('fetchHistory 映射 incomplete 字段', async () => {
    api.get.mockResolvedValue({
      data: {
        messages: [
          { id: 'u1', role: 'user', content: '问' },
          { id: 'a1', role: 'assistant', content: '半截', incomplete: true },
        ],
      },
    })
    await store.fetchHistory('s1')
    expect(store.messages[1].incomplete).toBe(true)
    expect(store.findIncompleteMessage()?.id).toBe('a1')
  })

  it('tryResumeIncomplete 对未完成消息调用 resume 并追加 token', async () => {
    store.messages = [
      { id: 'a1', role: 'assistant', content: '前半', incomplete: true },
    ]
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: sseStream([
        { type: 'resume_mode', mode: 'continue' },
        { type: 'token', content: '后半' },
        { type: 'done', message_id: 'a1' },
      ]),
    })

    const triggered = await store.tryResumeIncomplete()
    expect(triggered).toBe(true)
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/chat/messages/a1/resume?last_event_id=0',
      expect.anything()
    )
    expect(store.messages[0].content).toBe('前半后半')
    expect(store.messages[0].incomplete).toBe(false)
    expect(store.messages[0].isStreaming).toBe(false)
  })

  it('resume replay 模式用 answer 覆盖全文', async () => {
    store.messages = [
      { id: 'a2', role: 'assistant', content: '旧', incomplete: true },
    ]
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: sseStream([
        { type: 'resume_mode', mode: 'replay' },
        { type: 'answer', content: '完整重放正文' },
        { type: 'done' },
      ]),
    })

    await store.resumeMessageStream('a2')
    expect(store.messages[0].content).toBe('完整重放正文')
  })

  it('消息已完成时 tryResumeIncomplete 不触发', async () => {
    store.messages = [{ id: 'a3', role: 'assistant', content: '完整', incomplete: false }]
    global.fetch = vi.fn()
    const triggered = await store.tryResumeIncomplete()
    expect(triggered).toBe(false)
    expect(global.fetch).not.toHaveBeenCalled()
  })
})
