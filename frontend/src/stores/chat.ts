import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import api, { cancelAll } from '../services/api'
import type { Source } from '../types/models'

/** 反思/思考步骤（后端 thinking 事件负载） */
export interface ThinkingStep {
  step: number | string
  detail: string
}

/**
 * 流式消息的运行时形态。
 * 与 models.ChatMessage 的差异：thinking 在流式期间是步骤数组
 * （models 里为 string），另携带来源索引等扩展字段。
 */
export interface ChatStreamMessage {
  id: number | string
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  used_source_indices?: number[]
  filtered_sources?: Source[]
  expandedSources?: boolean
  created_at?: string
  isStreaming?: boolean
  thinking?: string | ThinkingStep[]
}

/** 会话列表条目（后端以 session_id 为键，区别于 models.ChatSession.id） */
export interface ChatSessionSummary {
  session_id: string
  title: string
  created_at?: string
  message_count?: number
}

/** SSE data 负载（宽松键位，按 type 分发） */
interface SseEvent {
  type: string
  session_id?: string
  sources?: Source[]
  filtered_sources?: Source[]
  content?: string
  step?: number | string
  detail?: string
  [key: string]: unknown
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatStreamMessage[]>([])
  const sessions = ref<ChatSessionSummary[]>([])
  const currentSession = ref<string | null>(null)
  const currentSessionTitle = ref('')
  const loading = ref(false)
  const isStreaming = ref(false) // 是否正在流式输出
  const abortController = ref<AbortController | null>(null) // 用于取消流式请求
  const lastFetched = ref(0)

  function isCacheFresh(): boolean {
    return Date.now() - lastFetched.value < 30_000
  }

  async function fetchSessions(forceRefresh = false): Promise<void> {
    if (!forceRefresh && isCacheFresh() && sessions.value.length > 0) return
    try {
      const response = await api.get<ChatSessionSummary[]>('/chat/history')
      sessions.value = response.data
      lastFetched.value = Date.now()
    } catch (error) {
      console.error('Error fetching sessions:', error)
      throw error
    }
  }

  async function fetchHistory(sessionId: string): Promise<void> {
    loading.value = true
    try {
      const response = await api.get<{ messages: ChatStreamMessage[] }>(
        `/chat/history/${sessionId}`
      )
      messages.value = response.data.messages
      currentSession.value = sessionId
      lastFetched.value = Date.now()
    } catch (error) {
      console.error('Error fetching history:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  const config = reactive({
    apiKey: localStorage.getItem('llmApiKey') || '',
    baseUrl: localStorage.getItem('llmBaseUrl') || 'https://api.openai.com/v1',
    provider: localStorage.getItem('llmProvider') || 'openrouter',
    modelName: localStorage.getItem('llmModel') || 'gpt-4o-mini',
    temperature: parseFloat(localStorage.getItem('llmTemperature') || '') || 0.7,
    maxTokens: parseInt(localStorage.getItem('llmMaxTokens') || '', 10) || 2048,
    adapter: localStorage.getItem('llmAdapter') || 'none'
  })

  function saveConfig(): void {
    localStorage.setItem(
      'llmConfig',
      JSON.stringify({
        provider: config.provider,
        modelName: config.modelName,
        temperature: config.temperature,
        maxTokens: config.maxTokens,
        adapter: config.adapter
      })
    )
  }

  async function askQuestion(
    question: string,
    documentIds: string[],
    sessionId: string | null = null
  ): Promise<any> {
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
        role: 'assistant' as const,
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

  async function askQuestionStream(
    question: string,
    documentIds: string[],
    sessionId: string | null = null
  ): Promise<{ success: boolean; cancelled?: boolean }> {
    loading.value = true
    isStreaming.value = true

    // 创建 AbortController 用于取消流式请求
    const controller = new AbortController()
    abortController.value = controller

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

    async function doFetch(token: string | null): Promise<Response> {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`
      return await fetch('/api/chat/ask', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          question,
          document_ids: documentIds,
          session_id: sessionId || currentSession.value,
          stream: true
        }),
        signal: controller.signal
      })
    }

    try {
      let token = localStorage.getItem('token')
      let response = await doFetch(token)

      // Auto-refresh on 401: try refreshing the token once
      if (response.status === 401) {
        const refreshToken = localStorage.getItem('refreshToken')
        if (refreshToken) {
          try {
            const refreshResp = await fetch('/api/auth/refresh', {
              method: 'POST',
              headers: { Authorization: `Bearer ${refreshToken}` }
            })
            if (refreshResp.ok) {
              const data = await refreshResp.json()
              localStorage.setItem('token', data.access_token)
              localStorage.setItem('refreshToken', data.refresh_token)
              response = await doFetch(data.access_token)
            }
          } catch (_) {
            // refresh failed, fall through to original error
          }
        }
      }

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()! // 保留未完成的行

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            let data: SseEvent
            try {
              data = JSON.parse(line.slice(6))
            } catch (e) {
              console.warn('Malformed SSE data, skipping line:', line, e)
              continue
            }

            if (data.type === 'session') {
              // 后端下发的会话 ID —— 多轮追问的关键：
              // 新对话时后端创建 session 后立即通知前端，
              // 后续消息才能带上同一 session_id 形成上下文
              if (data.session_id) {
                currentSession.value = data.session_id
              }
            } else if (data.type === 'sources') {
              // 更新临时消息的来源信息
              const msgIdx = messages.value.findIndex(m => m.id === tempMsgId)
              if (msgIdx !== -1) {
                messages.value[msgIdx].sources = data.sources
                messages.value[msgIdx].filtered_sources = data.filtered_sources
              }
            } else if (data.type === 'token') {
              // 实时更新临时消息内容（增量累加）
              const msgIdx = messages.value.findIndex(m => m.id === tempMsgId)
              if (msgIdx !== -1) {
                messages.value[msgIdx].content += data.content ?? ''
              }
            } else if (data.type === 'answer') {
              // 非流式答案（DIRECT_ANSWER / OUT_OF_SCOPE / SUMMARY 路径）
              const msgIdx = messages.value.findIndex(m => m.id === tempMsgId)
              if (msgIdx !== -1) {
                messages.value[msgIdx].content = data.content || ''
              }
            } else if (data.type === 'thinking') {
              // 思考过程事件（Agentic RAG）—— 追加到步骤数组
              const msgIdx = messages.value.findIndex(m => m.id === tempMsgId)
              if (msgIdx !== -1) {
                const m = messages.value[msgIdx]
                if (!Array.isArray(m.thinking)) m.thinking = []
                m.thinking.push({ step: data.step!, detail: data.detail! })
              }
            } else if (data.type === 'answer_refined') {
              // 答案反思后修正（替换已流式输出的内容）
              const msgIdx = messages.value.findIndex(m => m.id === tempMsgId)
              if (msgIdx !== -1) {
                messages.value[msgIdx].content = data.content || ''
              }
            } else if (data.type === 'done') {
              // 流式结束，更新最终状态
              const msgIdx = messages.value.findIndex(m => m.id === tempMsgId)
              if (msgIdx !== -1) {
                messages.value[msgIdx].isStreaming = false
              }
              // 新会话首次回答完成后，刷新历史列表让侧栏能看到它
              if (
                currentSession.value &&
                !sessions.value.some(s => s.session_id === currentSession.value)
              ) {
                fetchSessions().catch(() => {})
              }
            }
          }
        }
      }

      // 仅当调用方显式指定 session 时才覆盖；
      // 否则保留后端通过 session/sources 事件下发的 currentSession
      if (sessionId) {
        currentSession.value = sessionId
      }
      return { success: true }
    } catch (error: any) {
      if (error?.name === 'AbortError') {
        // 用户主动取消，不是错误 — 保留已流式传输的内容
        const msgIdx = messages.value.findIndex(m => m.id === tempMsgId)
        if (msgIdx !== -1) {
          messages.value[msgIdx].isStreaming = false
          // 如果没有任何内容，移除占位消息
          if (!messages.value[msgIdx].content) {
            messages.value = messages.value.filter(m => m.id !== tempMsgId)
          }
        }
        return { success: false, cancelled: true }
      }
      console.error('Error in streaming ask:', error)
      // 移除临时消息
      messages.value = messages.value.filter(m => m.id !== tempMsgId)
      throw error
    } finally {
      loading.value = false
      isStreaming.value = false
      // 清理该流式请求产生的所有待发请求（含自动重发）
      cancelAll()
      abortController.value = null
    }
  }

  function cancelStream(): void {
    if (abortController.value) {
      abortController.value.abort()
    }
  }

  async function deleteSession(sessionId: string): Promise<void> {
    try {
      await api.delete(`/chat/history/${sessionId}`)
      sessions.value = sessions.value.filter(s => s.session_id !== sessionId)
    } catch (error) {
      console.error('Error deleting session:', error)
      throw error
    }
  }

  async function updateSessionTitle(sessionId: string, title: string): Promise<void> {
    try {
      await api.put(`/chat/history/${sessionId}`, { title })
      const session = sessions.value.find(s => s.session_id === sessionId)
      if (session) {
        session.title = title
      }
    } catch (error) {
      console.error('Error updating session title:', error)
      throw error
    }
  }

  function clearMessages(): void {
    messages.value = []
  }

  return {
    messages,
    sessions,
    currentSession,
    currentSessionTitle,
    loading,
    config,
    saveConfig,
    lastFetched,
    fetchSessions,
    fetchHistory,
    askQuestion,
    askQuestionStream,
    cancelStream,
    deleteSession,
    updateSessionTitle,
    clearMessages,
    isStreaming
  }
})
