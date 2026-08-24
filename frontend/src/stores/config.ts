import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../services/api'
import { useChatStore } from './chat'
import type { LLMConfig } from '../types/models'

export const useConfigStore = defineStore('config', () => {
  const loading = ref(false)

  async function fetchLLMConfig(): Promise<LLMConfig | null> {
    try {
      const response = await api.get<LLMConfig>('/config/llm')
      const data = response.data

      if (data.provider) {
        localStorage.setItem('llmProvider', data.provider)
        localStorage.setItem('llmModel', data.model_name)
        localStorage.setItem('llmTemperature', (data.temperature || 0.7).toString())
        localStorage.setItem('llmMaxTokens', (data.max_tokens || 2048).toString())
      }
      return data
    } catch (error) {
      console.error('Failed to fetch LLM config:', error)
      return null
    }
  }

  // 安全修复（2026-08-19）：不再提供 fetchLLMConfigWithSecret。
  // 后端已移除 /config/llm/with-secret 端点（明文 Key 出网风险）；
  // 聊天/出题/转换所需的 Key 由后端服务端自行解密使用，前端永不需要明文。

  async function saveLLMConfig(configData: LLMConfig): Promise<LLMConfig> {
    loading.value = true
    try {

      const payload = {
        ...configData,
        temperature: configData.temperature || 0.7
      }

      const existing = await fetchLLMConfig()
      let response

      if (existing && existing.provider) {
        response = await api.put<LLMConfig>('/config/llm', payload)
      } else {
        response = await api.post<LLMConfig>('/config/llm', payload)
      }

      localStorage.setItem('llmProvider', configData.provider)
      localStorage.setItem('llmModel', configData.model_name)
      localStorage.setItem('llmTemperature', (configData.temperature || 0.7).toString())
      localStorage.setItem('llmMaxTokens', (configData.max_tokens || 2048).toString())

      const chatStore = useChatStore()
      chatStore.config.provider = configData.provider
      chatStore.config.modelName = configData.model_name
      chatStore.config.temperature = configData.temperature || 0.7
      chatStore.config.maxTokens = configData.max_tokens || 2048
      // apiKey 不再同步到 chatStore：请求不携带 Key，后端服务端自行解密使用
      chatStore.config.baseUrl = configData.base_url || ''

      return response.data
    } catch (error) {
      console.error('Failed to save LLM config:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function syncToChatStore(): Promise<void> {
    // 改用不含明文的 /config/llm；apiKey 不再下发（后端服务端使用）
    const config = await fetchLLMConfig()
    if (config && config.provider) {
      const chatStore = useChatStore()
      chatStore.config.provider = config.provider
      chatStore.config.baseUrl = config.base_url || ''
      chatStore.config.modelName = config.model_name
      chatStore.config.temperature = config.temperature || 0.7
      chatStore.config.maxTokens = config.max_tokens || 2048

      localStorage.setItem('llmProvider', config.provider)
      localStorage.setItem('llmModel', config.model_name)
      localStorage.setItem('llmTemperature', (config.temperature || 0.7).toString())
      localStorage.setItem('llmMaxTokens', (config.max_tokens || 2048).toString())
    }
  }

  return {
    loading,
    fetchLLMConfig,
    saveLLMConfig,
    syncToChatStore
  }
})
