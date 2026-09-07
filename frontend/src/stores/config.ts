import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../services/api'
import { useChatStore } from './chat'
import type { LLMConfig, SystemStatus, LLMCapabilities } from '../types/models'

/**
 * LLM 配置 store（P3-1 收敛后）。
 *
 * 状态源说明：服务端 /config/llm 是唯一配置事实源（Key 由后端 Fernet
 * 加密存储、服务端解密使用，前端请求不携带任何凭证）。
 * chatStore.config 仅作为 UI 回显镜像，由本 store 单向写入；
 * 曾经的 llmProvider/llmModel/llmTemperature/llmMaxTokens localStorage
 * 读写链已全部移除（配置不再从客户端读回）。
 */
export const useConfigStore = defineStore('config', () => {
  const loading = ref(false)

  async function fetchLLMConfig(): Promise<LLMConfig | null> {
    try {
      const response = await api.get<LLMConfig>('/config/llm')
      return response.data
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

      if (existing && existing.id) {
        response = await api.put<LLMConfig>('/config/llm', payload)
      } else {
        response = await api.post<LLMConfig>('/config/llm', payload)
      }

      // 单向同步到 chatStore 回显镜像（P3-1：唯一写入方）
      const chatStore = useChatStore()
      chatStore.config.provider = configData.provider
      chatStore.config.modelName = configData.model_name
      chatStore.config.temperature = configData.temperature || 0.7
      chatStore.config.maxTokens = configData.max_tokens || 2048
      chatStore.config.baseUrl = configData.base_url || ''
      chatStore.config.messageFormat = (configData as any).message_format || 'openai'

      return response.data
    } catch (error) {
      console.error('Failed to save LLM config:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function syncToChatStore(): Promise<void> {
    // 拉取服务端配置（不含明文 Key）并同步到 chatStore 回显镜像
    const config = await fetchLLMConfig()
    if (config && config.provider) {
      const chatStore = useChatStore()
      chatStore.config.provider = config.provider
      chatStore.config.baseUrl = config.base_url || ''
      chatStore.config.modelName = config.model_name
      chatStore.config.temperature = config.temperature || 0.7
      chatStore.config.maxTokens = config.max_tokens || 2048
      chatStore.config.messageFormat = config.message_format || 'openai'
    }
  }

  async function testLLMConfig(testData: {
    provider: string
    api_key?: string
    base_url?: string
    model_name: string
    message_format?: string
  }): Promise<{
    success: boolean
    message: string
    reply?: string
    latency_ms?: number
    capabilities?: LLMCapabilities
  }> {
    try {
      const response = await api.post<{
        success: boolean
        message: string
        reply?: string
        latency_ms?: number
        capabilities?: LLMCapabilities
      }>('/config/test-llm', testData)
      return response.data
    } catch (error: any) {
      return {
        success: false,
        message: error.response?.data?.detail || error.message || '网络连接异常'
      }
    }
  }

  async function getSystemStatus(): Promise<SystemStatus | null> {
    try {
      const response = await api.get<SystemStatus>('/config/system-status')
      return response.data
    } catch (error) {
      console.error('Failed to get system status:', error)
      return null
    }
  }

  async function detectLLMCapabilities(payload: {
    provider: string
    api_key?: string
    base_url?: string
    model_name: string
    message_format?: string
  }): Promise<LLMCapabilities | null> {
    try {
      const response = await api.post<LLMCapabilities>('/config/detect-llm', payload)
      return response.data
    } catch (error) {
      console.error('Failed to detect LLM capabilities:', error)
      return null
    }
  }

  async function testImageConfig(testData: {
    image_provider: string
    image_api_key?: string
    image_base_url?: string
    image_model: string
  }): Promise<{
    success: boolean
    message: string
    latency_ms?: number
  }> {
    try {
      const response = await api.post<{
        success: boolean
        message: string
        latency_ms?: number
      }>('/config/test-image', testData)
      return response.data
    } catch (error: any) {
      return {
        success: false,
        message: error.response?.data?.detail || error.message || '网络连接异常'
      }
    }
  }

  async function testTTSConfig(testData: {
    tts_provider: string
    tts_api_key?: string
    tts_base_url?: string
    tts_model?: string
    voice_teacher?: string
  }): Promise<{
    success: boolean
    message: string
    latency_ms?: number
    audio_base64?: string | null
  }> {
    try {
      const response = await api.post<{
        success: boolean
        message: string
        latency_ms?: number
        audio_base64?: string | null
      }>('/config/test-tts', testData)
      return response.data
    } catch (error: any) {
      return {
        success: false,
        message: error.response?.data?.detail || error.message || '语音服务连接异常',
        audio_base64: null
      }
    }
  }

  return {
    loading,
    fetchLLMConfig,
    saveLLMConfig,
    syncToChatStore,
    testLLMConfig,
    testImageConfig,
    testTTSConfig,
    getSystemStatus,
    detectLLMCapabilities
  }
})
