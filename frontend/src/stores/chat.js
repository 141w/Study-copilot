import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import api from '../services/api'

export const useChatStore = defineStore('chat', () => {
  const messages = ref([])
  const sessions = ref([])
  const currentSession = ref(null)
  const currentSessionTitle = ref('')
  const loading = ref(false)
  const streamingContent = ref('') // 新增：流式内容暂存
  const streamingSources = ref([]) // 新增：流式来源信息
  const isStreaming = ref(false) // 新增：是否正在流式输出
  const config = reactive({
    apiKey: localStorage.getItem('llmApiKey') || '',
    baseUrl: localStorage.getItem('llmBaseUrl') || 'https://api.openai.com/v1',
    provider: localStorage.getItem('llmProvider') || 'openrouter',
    modelName: localStorage.getItem('llmModel') || 'gpt-4o-mini',
    temperature: parseFloat(localStorage.getItem('llmTemperature')) || 0.7,
    maxTokens: parseInt(localStorage.getItem('llmMaxTokens')) || 2048,
    adapter: localStorage.getItem('llmAdapter') || 'none'
  })
  
  async function fetchSessions() {
    try {
      const response = await api.get('/chat/history')
      sessions.value = response.data
    } catch (error) {
      console.error('Error fetching sessions:', error)
    }
  }
  
  async function fetchHistory(sessionId) {
    loading.value = true
    try {
      const response = await api.get(`/chat/history/${sessionId}`)
      messages.value = response.data.messages
      currentSession.value = sessionId
    } catch (error) {
      console.error('Error fetching history:', error)
    } finally {
      loading.value = false
    }
  }
  
  function saveConfig() {
    localStorage.setItem('llmConfig', JSON.stringify({
      provider: config.provider,
      modelName: config.modelName,
      temperature: config.temperature,
      maxTokens: config.maxTokens,
      adapter: config.adapter
    }))
  }

  async function askQuestion(question, documentIds, sessionId = null) {
    loading.value = true

    messages.value.push({
      id: Date.now(),
      role: 'user',
      content: question,
      created_at: new Date().toISOString()
    })

    try {
      const response = await api.post('/chat/ask', {
        question,
        document_ids: documentIds,
        session_id: sessionId || currentSession.value,
        stream: false // 使用非流式接口
      })
      
      currentSession.value = response.data.session_id
      
      messages.value.push({
        id: Date.now() + 1,
        role: 'assistant',
        content: response.data.answer,
        sources: response.data.sources,
        used_source_indices: response.data.used_source_indices || [],
        filtered_sources: response.data.filtered_sources || [],
        expandedSources: false,
        created_at: new Date().toISOString()
      })
      
      return response.data
    } catch (error) {
      console.error('Error asking question:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function askQuestionStream(question, documentIds, sessionId = null) {
    loading.value = true
    isStreaming.value = true
    streamingContent.value = ''
    streamingSources.value = []

    // 先添加用户消息
    messages.value.push({
      id: Date.now(),
      role: 'user',
      content: question,
      created_at: new Date().toISOString()
    })

    // 创建临时AI消息占位
    const tempMsgId = Date.now() + 1
    messages.value.push({
      id: tempMsgId,
      role: 'assistant',
      content: '',
      sources: [],
      used_source_indices: [],
      filtered_sources: [],
      expandedSources: false,
      created_at: new Date().toISOString(),
      isStreaming: true // 标记为流式加载中
    })

    try {
      const token = localStorage.getItem('token')
      const headers = token ? { 'Authorization': `Bearer ${token}` } : {}
      
      const response = await fetch('/api/chat/ask', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...headers
        },
        body: JSON.stringify({
          question,
          document_ids: documentIds,
          session_id: sessionId || currentSession.value,
          stream: true
        })
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() // 保留未完成的行
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6))
            
            if (data.type === 'sources') {
              streamingSources.value = data.sources
              // 更新临时消息的来源信息
              const msgIdx = messages.value.findIndex(m => m.id === tempMsgId)
              if (msgIdx !== -1) {
                messages.value[msgIdx].sources = data.sources
                messages.value[msgIdx].filtered_sources = data.filtered_sources
              }
            } else if (data.type === 'token') {
              streamingContent.value += data.content
              // 实时更新临时消息内容
              const msgIdx = messages.value.findIndex(m => m.id === tempMsgId)
              if (msgIdx !== -1) {
                messages.value[msgIdx].content = streamingContent.value
              }
            } else if (data.type === 'done') {
              // 流式结束，更新最终状态
              const msgIdx = messages.value.findIndex(m => m.id === tempMsgId)
              if (msgIdx !== -1) {
                messages.value[msgIdx].isStreaming = false
              }
            }
          }
        }
      }

      currentSession.value = sessionId || currentSession.value
      return { success: true }
    } catch (error) {
      console.error('Error in streaming ask:', error)
      // 移除临时消息
      messages.value = messages.value.filter(m => m.id !== tempMsgId)
      throw error
    } finally {
      loading.value = false
      isStreaming.value = false
    }
  }

  async function deleteSession(sessionId) {
    try {
      await api.delete(`/chat/history/${sessionId}`)
      sessions.value = sessions.value.filter(s => s.session_id !== sessionId)
    } catch (error) {
      console.error('Error deleting session:', error)
      throw error
    }
  }

  async function updateSessionTitle(sessionId, title) {
    try {
      await api.put(`/chat/history/${sessionId}`, { title })
      const session = sessions.value.find(s => s.session_id === sessionId)
      if (session) {
        session.title = title
      }
    } catch (error) {
      console.error('Error updating title:', error)
      throw error
    }
  }
  
  function clearMessages() {
    messages.value = []
  }
  
  return {
    messages,
    sessions,
    currentSession,
    loading,
    config,
    saveConfig,
    fetchSessions,
    fetchHistory,
    askQuestion,
    askQuestionStream,
    deleteSession,
    updateSessionTitle,
    clearMessages,
    streamingContent,
    streamingSources,
    isStreaming
  }
})