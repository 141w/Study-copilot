import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../services/api'
import { useChatStore } from './chat'

export const useConfigStore = defineStore('config', () => {
  const loading = ref(false)

  async function fetchLLMConfig() {
    try {
      const response = await api.get('/config/llm')
      const data = response.data

      if (data.id) {
        localStorage.setItem('llmProvider', data.provider)
        localStorage.setItem('llmModel', data.model_name)
        localStorage.setItem('llmTemperature', data.temperature.toString())
        localStorage.setItem('llmMaxTokens', data.max_tokens.toString())
      }
      return data
    } catch (error) {
      console.error('Failed to fetch LLM config:', error)
      return null
    }
  }

  async function fetchLLMConfigWithSecret() {
    try {
      const response = await api.get('/config/llm/with-secret')
      return response.data
    } catch (error) {
      console.error('Failed to fetch LLM config with secret:', error)
      return null
    }
  }

  async function saveLLMConfig(configData) {
    loading.value = true
    try {
      const existing = await fetchLLMConfig()
      let response

      if (existing && existing.id) {
        response = await api.put('/config/llm', configData)
      } else {
        response = await api.post('/config/llm', configData)
      }

      localStorage.setItem('llmProvider', configData.provider)
      localStorage.setItem('llmModel', configData.model_name)
      localStorage.setItem('llmTemperature', configData.temperature.toString())
      localStorage.setItem('llmMaxTokens', configData.max_tokens.toString())

      const chatStore = useChatStore()
      chatStore.config.provider = configData.provider
      chatStore.config.modelName = configData.model_name
      chatStore.config.temperature = configData.temperature / 10
      chatStore.config.maxTokens = configData.max_tokens
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

  async function syncToChatStore() {
    const config = await fetchLLMConfigWithSecret()
    if (config && config.id) {
      const chatStore = useChatStore()
      chatStore.config.provider = config.provider
      chatStore.config.apiKey = config.api_key || ''
      chatStore.config.baseUrl = config.base_url || ''
      chatStore.config.modelName = config.model_name
      chatStore.config.temperature = config.temperature / 10
      chatStore.config.maxTokens = config.max_tokens

      localStorage.setItem('llmProvider', config.provider)
      localStorage.setItem('llmModel', config.model_name)
      localStorage.setItem('llmTemperature', config.temperature.toString())
      localStorage.setItem('llmMaxTokens', config.max_tokens.toString())
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