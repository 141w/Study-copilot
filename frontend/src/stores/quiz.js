import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../services/api'

export const useQuizStore = defineStore('quiz', () => {
  const quizzes = ref([])
  const currentQuiz = ref(null)
  const loading = ref(false)
  const quizResults = ref([])
  
  async function generateQuizzes(documentIds, choiceCount = 3, shortAnswerCount = 2) {
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
  
  async function submitAnswer(quizId, userAnswer) {
    try {
      const response = await api.post('/quiz/submit', {
        quiz_id: quizId,
        user_answer: userAnswer
      })

      const result = response.data

      const quiz = quizzes.value.find(q => q.id === quizId)
      if (quiz) {
        quiz.user_answer = userAnswer
        quiz.result = result
      }

      await fetchQuizHistory()

      return result
    } catch (error) {
      console.error('Error submitting answer:', error)
      throw error
    }
  }
  
  async function fetchQuizHistory() {
    try {
      const response = await api.get('/quiz/history')
      quizResults.value = response.data
    } catch (error) {
      console.error('Error fetching quiz history:', error)
    }
  }
  
  function setCurrentQuiz(quiz) {
    currentQuiz.value = quiz
  }
  
  function clearQuizzes() {
    quizzes.value = []
    currentQuiz.value = null
  }
  
  return {
    quizzes,
    currentQuiz,
    loading,
    quizResults,
    generateQuizzes,
    submitAnswer,
    fetchQuizHistory,
    setCurrentQuiz,
    clearQuizzes
  }
})