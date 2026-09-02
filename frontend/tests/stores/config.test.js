import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock the api module
vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

import { setActivePinia, createPinia } from 'pinia'
import { useConfigStore } from '@/stores/config'
import { useChatStore } from '@/stores/chat'
import api from '@/services/api'

describe('Config Store', () => {
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useConfigStore()
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('has correct initial state', () => {
    expect(store.loading).toBe(false)
  })

  it('fetchLLMConfig loads config and stores to localStorage', async () => {
    const config = {
      provider: 'openai',
      model_name: 'gpt-4',
      temperature: 0.7,
      max_tokens: 2048,
      base_url: 'https://api.openai.com/v1',
    }
    api.get.mockResolvedValue({ data: config })

    const result = await store.fetchLLMConfig()

    expect(result).toEqual(config)
    // P3-1：配置不再写 localStorage（服务端为唯一事实源）
    expect(localStorage.setItem).not.toHaveBeenCalled()
  })

  it('fetchLLMConfig returns null on error', async () => {
    api.get.mockRejectedValue(new Error('Network error'))

    const result = await store.fetchLLMConfig()

    expect(result).toBeNull()
  })

  it('fetchLLMConfig does not store when provider is missing', async () => {
    api.get.mockResolvedValue({ data: { provider: null } })

    await store.fetchLLMConfig()

    expect(localStorage.setItem).not.toHaveBeenCalled()
  })

  it('saveLLMConfig posts new config when none exists', async () => {
    api.get.mockResolvedValue({ data: { provider: null } })
    api.post.mockResolvedValue({
      data: { provider: 'openai', model_name: 'gpt-4', temperature: 0.8, max_tokens: 4096 },
    })

    const config = {
      provider: 'openai',
      model_name: 'gpt-4',
      temperature: 0.8,
      max_tokens: 4096,
      base_url: 'https://api.openai.com/v1',
    }
    const result = await store.saveLLMConfig(config)

    expect(api.post).toHaveBeenCalledWith('/config/llm', expect.objectContaining({
      provider: 'openai',
      model_name: 'gpt-4',
    }))
    expect(api.put).not.toHaveBeenCalled()
  })

  it('saveLLMConfig puts existing config', async () => {
    // 判据是 existing.id（后端 /config/llm 已保存时返回 id），mock 需带 id 走 PUT 分支
    api.get.mockResolvedValue({ data: { id: 'cfg-1', provider: 'openai', model_name: 'gpt-3.5' } })
    api.put.mockResolvedValue({
      data: { provider: 'openai', model_name: 'gpt-4', temperature: 0.9 },
    })

    const config = { provider: 'openai', model_name: 'gpt-4', temperature: 0.9, max_tokens: 2048 }
    await store.saveLLMConfig(config)

    expect(api.put).toHaveBeenCalledWith('/config/llm', expect.objectContaining({
      provider: 'openai',
      model_name: 'gpt-4',
    }))
  })

  it('saveLLMConfig sets loading during operation', async () => {
    let resolvePromise
    const promise = new Promise(resolve => { resolvePromise = resolve })
    api.get.mockReturnValue(promise)
    api.post.mockReturnValue(promise)

    const savePromise = store.saveLLMConfig({
      provider: 'openai', model_name: 'gpt-4', temperature: 0.7, max_tokens: 2048,
    })

    expect(store.loading).toBe(true)
    resolvePromise({ data: { provider: 'openai', model_name: 'gpt-4' } })
    await savePromise
    expect(store.loading).toBe(false)
  })

  it('syncToChatStore updates chat store with config', async () => {
    api.get.mockResolvedValue({
      data: { provider: 'openai', model_name: 'gpt-4', temperature: 0.8, max_tokens: 4096, base_url: 'https://api.openai.com/v1' },
    })
    const chatStore = useChatStore()

    await store.syncToChatStore()

    // P3-1：同步目标改为 chatStore.config 回显镜像（不再写 localStorage）
    expect(chatStore.config.provider).toBe('openai')
    expect(chatStore.config.modelName).toBe('gpt-4')
    expect(chatStore.config.temperature).toBe(0.8)
    expect(chatStore.config.maxTokens).toBe(4096)
    expect(localStorage.setItem).not.toHaveBeenCalled()
  })

  it('syncToChatStore handles missing config gracefully', async () => {
    api.get.mockResolvedValue({ data: { provider: null } })

    await store.syncToChatStore()

    expect(localStorage.setItem).not.toHaveBeenCalled()
  })
})
