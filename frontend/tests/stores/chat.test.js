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
import api from '@/services/api'

describe('Chat Store', () => {
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useChatStore()
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('has correct initial state', () => {
    expect(store.messages).toEqual([])
    expect(store.sessions).toEqual([])
    expect(store.currentSession).toBeNull()
    expect(store.loading).toBe(false)
    expect(store.isStreaming).toBe(false)
  })

  it('fetchSessions loads sessions from API', async () => {
    const mockSessions = [
      { session_id: 'sess-1', title: 'Session 1' },
      { session_id: 'sess-2', title: 'Session 2' },
    ]
    api.get.mockResolvedValue({ data: mockSessions })

    await store.fetchSessions()

    expect(api.get).toHaveBeenCalledWith('/chat/history')
    expect(store.sessions).toEqual(mockSessions)
  })

  it('askQuestion adds user and assistant messages', async () => {
    const mockResponse = {
      data: {
        session_id: 'new-session',
        answer: 'This is the answer',
        sources: [{ document_id: 'doc1', text: 'source text', relevance_score: 0.9 }],
        used_source_indices: [0],
        filtered_sources: [],
      },
    }
    api.post.mockResolvedValue(mockResponse)

    const result = await store.askQuestion('What is AI?', ['doc1'])

    expect(store.messages).toHaveLength(2)
    expect(store.messages[0].role).toBe('user')
    expect(store.messages[0].content).toBe('What is AI?')
    expect(store.messages[1].role).toBe('assistant')
    expect(store.messages[1].content).toBe('This is the answer')
    expect(store.messages[1].sources).toHaveLength(1)
    expect(store.currentSession).toBe('new-session')
    expect(result).toEqual(mockResponse.data)
  })

  it('clearMessages resets messages array', () => {
    store.messages.value = [
      { id: 1, role: 'user', content: 'hello' },
      { id: 2, role: 'assistant', content: 'hi' },
    ]

    store.clearMessages()

    expect(store.messages).toEqual([])
  })

  it('deleteSession removes session from list', async () => {
    store.sessions = [
      { session_id: 'sess-1', title: 'Session 1' },
      { session_id: 'sess-2', title: 'Session 2' },
    ]
    api.delete.mockResolvedValue({})

    await store.deleteSession('sess-1')

    expect(api.delete).toHaveBeenCalledWith('/chat/history/sess-1')
    expect(store.sessions).toHaveLength(1)
    expect(store.sessions[0].session_id).toBe('sess-2')
  })

  it('fetchHistory loads and normalizes discussion messages', async () => {
    const mockHistory = {
      messages: [
        { id: '1', role: 'user', content: 'Discuss AI ethics' },
        {
          id: '2',
          role: 'discussion',
          content: 'Full summary',
          discussion_turns: [
            { id: 't-1', persona: '苏老师', content: '道德优先', turn: 1 }
          ],
          summary: '总结结论',
        },
      ],
    }
    api.get.mockResolvedValue({ data: mockHistory })

    await store.fetchHistory('sess-1')

    expect(api.get).toHaveBeenCalledWith('/chat/history/sess-1')
    expect(store.currentSession).toBe('sess-1')
    expect(store.messages).toHaveLength(2)
    expect(store.messages[1].role).toBe('discussion')
    expect(store.messages[1].discussionTurns).toBeDefined()
    expect(store.messages[1].discussionTurns).toHaveLength(1)
    expect(store.messages[1].discussionTurns[0].persona).toBe('苏老师')
    expect(store.messages[1].summary).toBe('总结结论')
  })
})
