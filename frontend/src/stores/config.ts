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

  async function fetchLLMConfigWithSecret(): Promise<LLMConfig | null> {
    try {
      const response = await api.get<LLMConfig>('/config/llm/with-secret')
      return response.data
    } catch (error) {
      console.error('Failed to fetch LLM config with secret:', error)
      return null
    }
  }

  async function saveLLMConfig(configData: LLMConfig): Promise<LLMConfig> {
    loading.value = true
    try {
      // DB stores temperature as integer (7 for 0.7), so multiply by 10 when saving
      const payload = {
        ...configData,
        temperature: Math.round((configData.temperature || 0.7) * 10)
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
      if (configData.api_key) {
        chatStore.config.apiKey = configData.api_key
        chatStore.config.baseUrl = configData.base_url || ''
      }

      return response.data
    } catch (error) {
      console.error('Failed to save LLM config:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function syncToChatStore(): Promise<void> {
    const config = await fetchLLMConfigWithSecret()
    if (config && config.provider) {
      const chatStore = useChatStore()
      chatStore.config.provider = config.provider
      chatStore.config.apiKey = config.api_key || ''
      chatStore.config.baseUrl = config.base_url || ''
      chatStore.config.modelName = config.model
      chatStore.config.temperature = config.temperature || 0.7
      chatStore.config.maxTokens = config.max_tokens || 2048

      localStorage.setItem('llmProvider', config.provider)
      localStorage.setItem('llmModel', config.model)
      localStorage.setItem('llmTemperature', (config.temperature || 0.7).toString())
      localStorage.setItem('llmMaxTokens', (config.max_tokens || 2048).toString())
    }
  }

  return {
    loading,
    fetchLLMConfig,
    fetchLLMConfigWithSecret,
    saveLLMConfig,
    syncToChatStore
  }
})
