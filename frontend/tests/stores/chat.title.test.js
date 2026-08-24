import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock the api module before importing the store
vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

import { setActivePinia, createPinia } from 'pinia'
import { useChatStore } from '@/stores/chat'

/**
 * 回归测试：strict 模式（TS6133）揪出的隐性 bug——
 * useChatStore 曾未 return currentSessionTitle，导致 ChatView 四处读写全部落空
 * （头部标题显示 / 导出文件名 / 新会话清空 / 切换会话恢复）。
 */
describe('Chat Store currentSessionTitle 暴露（strict 回归守护）', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('store 实例上必须存在且可写 currentSessionTitle', () => {
    const store = useChatStore()
    expect('currentSessionTitle' in store).toBe(true)
    expect(store.currentSessionTitle).toBe('')
  })

  it('模拟 ChatView 生命周期：loadSession 写入 → exportChat 可读 → newChat 清空', () => {
    const store = useChatStore()

    // loadSession：切换会话后写入标题
    store.currentSessionTitle = '增值税实务讲义'
    // exportChat：读取标题作为导出文件名来源
    expect(store.currentSessionTitle).toBe('增值税实务讲义')

    // newChat：新会话清空标题
    store.currentSessionTitle = ''
    expect(store.currentSessionTitle).toBe('')
  })
})
