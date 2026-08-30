import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../services/api'
import type { Quiz } from '../types/models'

/** 提交答案后的判分结果（/quiz/submit 响应） */
export interface QuizSubmitResult {
  quiz_id: string
  user_answer: string
  correct_answer: string
  is_correct: boolean
  explanation?: string | null
}

/** 做题历史条目（/quiz/result-history 响应） */
export interface QuizHistoryItem {
  quiz_id: string
  question: string
  user_answer: string
  correct_answer: string
  is_correct: boolean
  submitted_at: string
}

/** 运行时测验题（在 models.Quiz 基础上叠加作答状态） */
export type RuntimeQuiz = Quiz & {
  user_answer?: string
  result?: QuizSubmitResult
}

export const useQuizStore = defineStore('quiz', () => {
  const quizzes = ref<RuntimeQuiz[]>([])
  const currentQuiz = ref<RuntimeQuiz | null>(null)
  const loading = ref(false)
  const quizResults = ref<QuizHistoryItem[]>([])
  const lastFetched = ref(0)

  function isCacheFresh(): boolean {
    return Date.now() - lastFetched.value < 30_000 && quizResults.value.length > 0
  }

  async function generateQuizzes(
    documentIds: string[],
    choiceCount: number = 3,
    shortAnswerCount: number = 2
  ): Promise<any> {
    loading.value = true
    try {
      const response = await api.post('/quiz/generate', {
        document_ids: documentIds,
        choice_count: choiceCount,
        short_answer_count: shortAnswerCount
      })

      quizzes.value = response.data.quizzes
      return response.data
    } catch (error) {
      console.error('Error generating quizzes:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function submitAnswer(quizId: string, userAnswer: string): Promise<QuizSubmitResult> {
    try {
      const response = await api.post<QuizSubmitResult>('/quiz/submit', {
        quiz_id: quizId,
        user_answer: userAnswer
      })

      const result = response.data

      const quiz = quizzes.value.find(q => q.id === quizId)
      if (quiz) {
        quiz.user_answer = userAnswer
        quiz.result = result
      }

      return result
    } catch (error) {
      console.error('Error submitting answer:', error)
      throw error
    }
  }

  async function fetchQuizHistory(forceRefresh = false): Promise<void> {
    if (!forceRefresh && isCacheFresh()) return
    try {
      const response = await api.get<QuizHistoryItem[]>('/quiz/result-history')
      quizResults.value = response.data
      lastFetched.value = Date.now()
    } catch (error) {
      console.error('Error fetching quiz history:', error)
      throw error
    }
  }

  function setCurrentQuiz(quiz: RuntimeQuiz | null): void {
    currentQuiz.value = quiz
  }

  function clearQuizzes(): void {
    quizzes.value = []
    currentQuiz.value = null
  }

  return {
    quizzes,
    currentQuiz,
    loading,
    quizResults,
    lastFetched,
    generateQuizzes,
    submitAnswer,
    fetchQuizHistory,
    setCurrentQuiz,
    clearQuizzes
  }
})
