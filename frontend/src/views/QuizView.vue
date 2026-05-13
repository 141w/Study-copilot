<template>
  <div class="max-w-3xl mx-auto px-6 py-8">
    <h1 class="text-2xl font-semibold text-gray-900 mb-8">做题练习</h1>
    
    <!-- Generate Quiz -->
    <div class="card p-6 mb-8">
      <h2 class="font-semibold text-gray-900 mb-4">生成题目</h2>

      <div class="mb-4">
        <label class="block text-sm text-gray-600 mb-2">选择文档</label>
        <div class="grid grid-cols-2 md:grid-cols-3 gap-2">
          <div
            v-for="doc in availableDocs"
            :key="doc.id"
            @click="toggleDoc(doc.id)"
            class="p-3 border rounded-lg cursor-pointer transition-all"
            :class="selectedDocs.includes(doc.id) ? 'border-[#010120] bg-gray-50' : 'border-gray-200'"
          >
            <p class="text-sm font-medium text-gray-900 truncate">{{ doc.filename }}</p>
            <p class="text-xs text-gray-500">状态: {{ doc.status }}</p>
          </div>
        </div>
        <p v-if="availableDocs.length === 0" class="text-sm text-gray-500">
          请先上传文档
        </p>
      </div>

      <div class="flex gap-4 items-end mb-4">
        <div class="flex-1">
          <label class="block text-sm text-gray-600 mb-2">选择题数量</label>
          <input
            v-model.number="config.choiceCount"
            type="number"
            min="1"
            max="10"
            class="input-field"
          />
        </div>

        <div class="flex-1">
          <label class="block text-sm text-gray-600 mb-2">简答题数量</label>
          <input
            v-model.number="config.shortAnswerCount"
            type="number"
            min="1"
            max="5"
            class="input-field"
          />
        </div>

        <button
          @click="generateQuiz"
          :disabled="quizStore.loading || selectedDocs.length === 0"
          class="btn-primary"
        >
          {{ quizStore.loading ? '生成中...' : '生成题目' }}
        </button>
      </div>

      <p class="text-sm text-gray-500">
        已选文档: {{ selectedDocs.length }} 个
      </p>
    </div>
    
    <!-- Quiz List -->
    <div v-if="quizStore.quizzes.length > 0" class="space-y-6">
      <div 
        v-for="(quiz, index) in quizStore.quizzes" 
        :key="quiz.id"
        class="card p-6"
      >
        <div class="flex items-start gap-3 mb-4">
          <span class="w-6 h-6 rounded-full bg-[#010120] text-white text-sm flex items-center justify-center flex-shrink-0">
            {{ index + 1 }}
          </span>
          <div class="flex-1">
            <span class="text-xs font-medium px-2 py-0.5 rounded bg-gray-100 text-gray-600">
              {{ quiz.question_type === 'choice' ? '选择题' : '简答题' }}
            </span>
            <h3 class="text-lg font-medium text-gray-900 mt-2">{{ quiz.question }}</h3>
          </div>
        </div>
        
        <!-- Choice Options -->
        <div v-if="quiz.question_type === 'choice' && quiz.options" class="space-y-2 mb-4 ml-9">
          <label 
            v-for="(option, idx) in quiz.options" 
            :key="idx"
            class="flex items-center gap-3 p-3 rounded-lg border cursor-pointer"
            :class="selectedAnswers[quiz.id] === option 
              ? 'border-[#010120] bg-gray-50' 
              : 'border-gray-200 hover:border-gray-300'"
          >
            <input 
              type="radio" 
              :name="quiz.id" 
              :value="option" 
              v-model="selectedAnswers[quiz.id]"
              class="hidden"
            />
            <span class="w-6 h-6 rounded-full border flex items-center justify-center text-sm"
              :class="selectedAnswers[quiz.id] === option 
                ? 'border-[#010120] bg-[#010120] text-white' 
                : 'border-gray-300'"
            >
              {{ ['A', 'B', 'C', 'D'][idx] }}
            </span>
            {{ option }}
          </label>
        </div>
        
        <!-- Short Answer Input -->
        <div v-else-if="quiz.question_type === 'short_answer'" class="mb-4 ml-9">
          <textarea
            v-model="selectedAnswers[quiz.id]"
            placeholder="请输入答案..."
            class="input-field h-24"
          ></textarea>
        </div>
        
        <!-- Submit Button -->
        <div class="ml-9">
          <button 
            @click="submitAnswer(quiz)"
            :disabled="!selectedAnswers[quiz.id] || quiz.submitted"
            class="btn-primary"
          >
            {{ quiz.submitted ? '已提交' : '提交答案' }}
          </button>
        </div>
        
        <!-- Result -->
        <div v-if="quiz.result" class="mt-4 ml-9 p-4 rounded-lg"
          :class="quiz.result.is_correct ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'"
        >
          <div class="flex items-center gap-2 mb-2">
            <svg v-if="quiz.result.is_correct" class="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
            </svg>
            <svg v-else class="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
            <span :class="quiz.result.is_correct ? 'text-green-700' : 'text-red-700'" class="font-medium">
              {{ quiz.result.is_correct ? '回答正确' : '回答错误' }}
            </span>
          </div>
          <p class="text-sm text-gray-600">
            正确答案: {{ quiz.result.correct_answer }}
          </p>
          <p v-if="quiz.result.explanation" class="text-sm text-gray-500 mt-2">
            解析: {{ quiz.result.explanation }}
          </p>
        </div>
      </div>
    </div>
    
    <div v-else class="text-center text-gray-400 py-12">
      <svg class="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
      </svg>
      <p>点击"生成题目"开始练习</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useQuizStore } from '../stores/quiz'
import { useDocumentStore } from '../stores/document'

const quizStore = useQuizStore()
const documentStore = useDocumentStore()

const name = 'QuizView'

const config = ref({
  choiceCount: 3,
  shortAnswerCount: 2
})

const selectedDocs = ref([])

const selectedAnswers = ref({})

const availableDocs = computed(() => {
  return documentStore.documents.filter(d => d.status === 'ready')
})

function toggleDoc(docId) {
  const idx = selectedDocs.value.indexOf(docId)
  if (idx > -1) {
    selectedDocs.value.splice(idx, 1)
  } else {
    selectedDocs.value.push(docId)
  }
}

async function generateQuiz() {
  if (selectedDocs.value.length === 0) return

  selectedAnswers.value = {}

  await quizStore.generateQuizzes(
    selectedDocs.value,
    config.value.choiceCount,
    config.value.shortAnswerCount
  )
}

async function submitAnswer(quiz) {
  const userAnswer = selectedAnswers.value[quiz.id]
  if (!userAnswer) return
  
  const result = await quizStore.submitAnswer(quiz.id, userAnswer)
  
  quizStore.quizzes.find(q => q.id === quiz.id).submitted = true
  quizStore.quizzes.find(q => q.id === quiz.id).result = result
}

onMounted(() => {
  documentStore.fetchDocuments()
})
</script>