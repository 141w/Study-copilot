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
import { useQuizStore } from '@/stores/quiz'
import api from '@/services/api'

describe('Quiz Store', () => {
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useQuizStore()
    vi.clearAllMocks()
  })

  it('has correct initial state', () => {
    expect(store.quizzes).toEqual([])
    expect(store.currentQuiz).toBeNull()
    expect(store.loading).toBe(false)
    expect(store.quizResults).toEqual([])
  })

  it('generateQuizzes fetches and stores quizzes', async () => {
    const mockQuizzes = [
      { id: 'q1', question: 'What is Vue?', type: 'choice', options: ['A', 'B', 'C'] },
      { id: 'q2', question: 'Explain Pinia', type: 'short_answer' },
    ]
    api.post.mockResolvedValue({ data: { quizzes: mockQuizzes } })

    const result = await store.generateQuizzes(['doc1'], 1, 1)

    expect(api.post).toHaveBeenCalledWith('/quiz/generate', {
      document_ids: ['doc1'],
      choice_count: 1,
      short_answer_count: 1,
    })
    expect(store.quizzes).toEqual(mockQuizzes)
    expect(result.quizzes).toEqual(mockQuizzes)
    expect(store.loading).toBe(false)
  })

  it('submitAnswer updates quiz with user answer and result', async () => {
    store.quizzes = [
      { id: 'q1', question: 'What is Vue?', type: 'choice' },
    ]
    const mockResult = { correct: true, explanation: 'Vue is a JS framework' }
    api.post.mockResolvedValue({ data: mockResult })

    const result = await store.submitAnswer('q1', 'A')

    expect(api.post).toHaveBeenCalledWith('/quiz/submit', {
      quiz_id: 'q1',
      user_answer: 'A',
    })
    expect(store.quizzes[0].user_answer).toBe('A')
    expect(store.quizzes[0].result).toEqual(mockResult)
    expect(result).toEqual(mockResult)
  })

  it('setCurrentQuiz and clearQuizzes work correctly', () => {
    const quiz = { id: 'q1', question: 'Test question' }
    store.setCurrentQuiz(quiz)
    expect(store.currentQuiz).toEqual(quiz)

    store.quizzes = [quiz]
    store.clearQuizzes()
    expect(store.quizzes).toEqual([])
    expect(store.currentQuiz).toBeNull()
  })
})
