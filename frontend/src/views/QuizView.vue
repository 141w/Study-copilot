<template>
  <div class="max-w-3xl mx-auto px-6 py-8">
    <h1 class="text-2xl font-semibold text-[var(--text-primary)] mb-8">做题练习</h1>

    <!-- Mode Toggle -->
    <div class="flex gap-2 mb-6">
      <el-button
        :type="!examMode ? 'primary' : 'default'"
        @click="examMode = false; examSubmitted = false"
      >
        练习模式
      </el-button>
      <el-button
        :type="examMode ? 'primary' : 'default'"
        @click="examMode = true; examSubmitted = false"
      >
        考试模式
      </el-button>
    </div>

    <!-- Generate Quiz -->
    <div class="card p-6 mb-8">
      <h2 class="font-semibold text-[var(--text-primary)] mb-4">生成题目</h2>

      <div class="mb-4">
        <label class="block text-sm text-[var(--text-secondary)] mb-2">选择文档</label>
        <!-- P2-3：DocumentPicker cards 模式（原为手写卡片网格） -->
        <DocumentPicker
          v-model="selectedDocs"
          mode="cards"
          :documents="availableDocs"
        />
      </div>

      <div class="flex gap-4 items-end mb-4">
        <div class="flex-1">
          <label for="quiz-choice-count" class="block text-sm text-[var(--text-secondary)] mb-2">选择题数量</label>
          <input
            id="quiz-choice-count"
            v-model.number="config.choiceCount"
            type="number"
            min="1"
            max="10"
            class="input"
          />
        </div>

        <div class="flex-1">
          <label for="quiz-short-count" class="block text-sm text-[var(--text-secondary)] mb-2">简答题数量</label>
          <input
            id="quiz-short-count"
            v-model.number="config.shortAnswerCount"
            type="number"
            min="1"
            max="5"
            class="input"
          />
        </div>

        <el-button
          @click="generateQuiz"
          :disabled="generating || quizStore.loading || selectedDocs.length === 0"
          type="primary"
        >
          {{ (generating || quizStore.loading) ? '生成中...' : '生成题目' }}
        </el-button>
      </div>

      <p class="text-sm text-[var(--text-muted)]">
        已选文档: {{ selectedDocs.length }} 个
      </p>
    </div>
    
    <!-- Quiz List -->
    <div ref="quizListRef" v-if="quizStore.quizzes.length > 0" class="space-y-6">
      <div
        v-for="(quiz, index) in quizStore.quizzes"
        :key="quiz.id"
        class="card p-6"
      >
        <div class="flex items-start gap-3 mb-4">
          <span class="w-6 h-6 rounded-full bg-[var(--color-primary)] text-[var(--text-inverse)] text-sm flex items-center justify-center flex-shrink-0">
            {{ index + 1 }}
          </span>
          <div class="flex-1">
            <span class="text-xs font-medium px-2 py-0.5 rounded bg-[var(--bg-tertiary)] text-[var(--text-secondary)]">
              {{ quiz.question_type === 'choice' ? '选择题' : '简答题' }}
            </span>
            <h3 class="text-lg font-medium text-[var(--text-primary)] mt-2">{{ quiz.question }}</h3>
          </div>
        </div>

        <!-- Choice Options -->
        <div v-if="quiz.question_type === 'choice' && quiz.options" class="space-y-2 mb-4 ml-9">
          <label
            v-for="(option, idx) in quiz.options"
            :key="idx"
            class="flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all active:scale-[0.98]"
            :class="selectedAnswers[quiz.id] === optionLetter(idx)
              ? 'border-[var(--color-primary)] bg-[var(--color-primary-light)]'
              : 'border-[var(--border-default)] hover:border-[var(--border-hover)]'"
          >
            <input
              type="radio"
              :name="quiz.id"
              :value="optionLetter(idx)"
              v-model="selectedAnswers[quiz.id]"
              class="hidden"
            />
            <span class="w-6 h-6 rounded-full border flex items-center justify-center text-sm"
              :class="selectedAnswers[quiz.id] === optionLetter(idx)
                ? 'border-[var(--color-primary)] bg-[var(--color-primary)] text-[var(--text-inverse)]'
                : 'border-[var(--border-default)]'"
            >
              {{ optionLetter(idx) }}
            </span>
            <span class="text-[var(--text-primary)]">{{ option }}</span>
          </label>
        </div>

        <!-- Short Answer Input -->
        <div v-else-if="quiz.question_type === 'short_answer'" class="mb-4 ml-9">
          <textarea
            v-model="selectedAnswers[quiz.id]"
            placeholder="请输入答案..."
            class="input h-24"
          ></textarea>
        </div>

        <!-- Submit Button (practice mode only) -->
        <div v-if="!examMode" class="ml-9">
          <el-button
            @click="submitAnswer(quiz)"
            :disabled="!selectedAnswers[quiz.id] || quiz.submitted || submitting[quiz.id]"
            type="primary"
          >
            {{ (quiz.submitted || submitting[quiz.id]) ? '提交中...' : '提交答案' }}
          </el-button>
        </div>

        <!-- Result -->
        <div v-if="quiz.result" class="mt-4 ml-9 p-4 rounded-lg"
          :class="quiz.result.is_correct ? 'bg-[var(--color-success-light)] border-2 border-[var(--color-success)]' : 'bg-[var(--color-error-light)] border-2 border-[var(--color-error)]'"
        >
          <div class="flex items-center gap-2 mb-2">
            <!-- 批次5：手写描边 SVG → EP 填充图标，与全站图标体系统一 -->
            <el-icon v-if="quiz.result.is_correct" class="w-5 h-5 text-[var(--color-success)]"><CircleCheckFilled /></el-icon>
            <el-icon v-else class="w-5 h-5 text-[var(--color-error)]"><CircleCloseFilled /></el-icon>
            <span :class="quiz.result.is_correct ? 'text-[var(--color-success)]' : 'text-[var(--color-error)]'" class="font-medium">
              {{ quiz.result.is_correct ? '回答正确' : '回答错误' }}
            </span>
          </div>
          <p class="text-sm text-[var(--text-secondary)]">
            正确答案: {{ formatAnswer(quiz, quiz.result.correct_answer) }}
          </p>
          <p v-if="quiz.result.explanation" class="text-sm text-[var(--text-muted)] mt-2">
            解析: {{ quiz.result.explanation }}
          </p>
        </div>
      </div>

      <!-- Exam Mode: Submit All & Summary -->
      <div v-if="examMode && !examSubmitted" class="text-center mt-6">
        <el-button
          @click="submitAll"
          :disabled="Object.keys(selectedAnswers).length === 0"
          type="primary"
        >
          交卷
        </el-button>
      </div>

      <div v-if="examMode && examSummary" class="card p-6 mt-6 !bg-[var(--color-primary-light)] border border-[var(--border-default)]">
        <h3 class="text-lg font-semibold text-[var(--text-primary)] mb-2">考试结果</h3>
        <p class="text-[var(--text-primary)]">
          正确 <span class="font-bold">{{ examSummary.correct }}</span> / {{ examSummary.total }} 题，
          正确率 <span class="font-bold">{{ examSummary.accuracy }}%</span>
        </p>
      </div>
    </div>

    <div v-else class="text-center text-[var(--text-muted)] py-12">
      <el-icon class="w-16 h-16 mx-auto mb-4"><DocumentChecked /></el-icon>
      <p>点击"生成题目"开始练习</p>
    </div>

    <!-- Wrong Questions Section -->
    <div class="mt-10">
      <el-button
        @click="loadWrongQuestions"
        :loading="loadingWrong"
      >
        {{ loadingWrong ? '加载中...' : '加载错题' }}
      </el-button>

      <div v-if="wrongQuestions.length > 0" class="space-y-4 mt-6">
        <h2 class="text-xl font-semibold text-[var(--text-primary)]">错题本</h2>
        <div
          v-for="q in wrongQuestions"
          :key="q.id"
          class="card p-5 border-l-4 border-[var(--color-error)]"
        >
          <h3 class="text-base font-medium text-[var(--text-primary)] mb-3">{{ q.question }}</h3>
          <div class="space-y-1 text-sm">
            <p class="text-[var(--color-error)]">你的答案: {{ formatAnswer(q, q.user_answer) }}</p>
            <p class="text-[var(--color-success)]">正确答案: {{ formatAnswer(q, q.correct_answer) }}</p>
            <p v-if="q.explanation" class="text-[var(--text-muted)]">解析: {{ q.explanation }}</p>
          </div>
          <el-button
            @click="redoQuestion(q)"
            type="primary"
          >
            重做此题
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// defineOptions 是编译器宏，无需导入
defineOptions({ name: 'QuizView' })

import { ref, computed, onMounted, watch, nextTick, onUnmounted } from 'vue'
import gsap from 'gsap'
import { DocumentChecked, CircleCheckFilled, CircleCloseFilled } from '@/components/icons'
import { useQuizStore } from '../stores/quiz'
import type { RuntimeQuiz, QuizSubmitResult } from '../stores/quiz'
import { useDocumentStore } from '../stores/document'
import DocumentPicker from '../components/common/DocumentPicker.vue'
import api from '../services/api'
import { useReducedMotion } from '../composables/useReducedMotion'

/** 错题条目（/quiz/wrong-questions 响应） */
interface WrongQuestion {
  id: string
  question: string
  question_type?: 'choice' | 'short_answer'
  options?: string[] | null
  user_answer: string
  correct_answer: string
  explanation?: string
}

const quizStore = useQuizStore()
const documentStore = useDocumentStore()
// P1-1：GSAP 动画降级（prefers-reduced-motion）
const { prefersReduced } = useReducedMotion()

const config = ref({
  choiceCount: 3,
  shortAnswerCount: 2
})

const selectedDocs = ref<string[]>([])

const selectedAnswers = ref<Record<string, string>>({})

const submitting = ref<Record<string, boolean>>({})

const examMode = ref(false)

const examSubmitted = ref(false)

const generating = ref(false)

const quizListRef = ref<HTMLElement | null>(null)

const wrongQuestions = ref<WrongQuestion[]>([])

const loadingWrong = ref(false)

const ctx = gsap.context(() => {})
const animatedResults = new Set<string>()

const availableDocs = computed(() => {
  return documentStore.documents.filter(d => d.status === 'ready')
})

/**
 * P0-7：选项按字母（索引）提交而非文本。
 * 后端 quiz.answer 只存字母（A/B/C/D），_judge_choice 按字母匹配；
 * 原实现按选项文本提交，遇到相同文本选项或文本型 options 数组必然判错。
 */
const OPTION_LETTERS = ['A', 'B', 'C', 'D', 'E', 'F']
function optionLetter(idx: number): string {
  return OPTION_LETTERS[idx] || String(idx)
}

watch(() => quizStore.quizzes.length, (newLen, oldLen) => {
  if (newLen > 0 && oldLen === 0) {
    // P1-1：减少动态偏好下跳过列表入场动画
    if (prefersReduced.value) return
    nextTick(() => {
      const cards = quizListRef.value?.querySelectorAll('.card')
      if (cards?.length) {
        ctx.add(() => {
          gsap.from(cards, {
            y: 30,
            opacity: 0,
            duration: 0.5,
            stagger: 0.1,
            ease: 'power2.out'
          })
        })
      }
    })
  }
})

watch(() => quizStore.quizzes.map(q => ({ id: q.id, result: q.result })), () => {
  // P1-1：减少动态偏好下跳过结果入场动画
  if (prefersReduced.value) return
  nextTick(() => {
    if (!quizListRef.value) return
    const cards = quizListRef.value.querySelectorAll('.card')
    quizStore.quizzes.forEach((quiz, i) => {
      if (quiz.result && !animatedResults.has(quiz.id)) {
        animatedResults.add(quiz.id)
        const resultDiv = cards[i]?.querySelector('.mt-4.ml-9.p-4.rounded-lg')
        if (resultDiv) {
          ctx.add(() => {
            gsap.from(resultDiv, {
              scale: 0.95,
              opacity: 0,
              duration: 0.3,
              ease: 'back.out(1.5)'
            })
          })
        }
      }
    })
  })
}, { deep: true })

async function generateQuiz(): Promise<void> {
  if (selectedDocs.value.length === 0 || generating.value) return

  generating.value = true
  selectedAnswers.value = {}
  examSubmitted.value = false

  try {
    await quizStore.generateQuizzes(
      selectedDocs.value,
      config.value.choiceCount,
      config.value.shortAnswerCount
    )
  } finally {
    generating.value = false
  }
}

/**
 * 答案展示：选择题把字母映射回「字母. 选项文本」；简答题原样返回。
 * 用于结果卡片与错题本（后端存的是字母）。
 */
function formatAnswer(
  quiz: { question_type?: string; options?: string[] | null },
  answer: string
): string {
  if (!answer) return ''
  if (quiz.question_type !== 'choice' || !quiz.options?.length) return answer
  const idx = OPTION_LETTERS.indexOf(answer.toUpperCase())
  if (idx === -1 || !quiz.options[idx]) return answer
  return `${OPTION_LETTERS[idx]}. ${quiz.options[idx]}`
}

async function submitAnswer(quiz: RuntimeQuiz): Promise<void> {
  const userAnswer = selectedAnswers.value[quiz.id]
  if (!userAnswer) return

  submitting.value[quiz.id] = true
  try {
    const result: QuizSubmitResult = await quizStore.submitAnswer(quiz.id, userAnswer)

    const target = quizStore.quizzes.find(q => q.id === quiz.id)
    if (target) {
      target.submitted = true
      target.result = result
    }
  } finally {
    submitting.value[quiz.id] = false
  }
}

const examSummary = computed<{ total: number; correct: number; accuracy: number } | null>(() => {
  if (!examSubmitted.value) return null
  const total = quizStore.quizzes.length
  const correct = quizStore.quizzes.filter(q => q.result?.is_correct).length
  const accuracy = total > 0 ? Math.round((correct / total) * 100) : 0
  return { total, correct, accuracy }
})

async function submitAll(): Promise<void> {
  // P1-6（顺带在 P0 批次一起修）：并行提交——考试模式交卷不再逐题串行等待
  const pending = quizStore.quizzes.filter(
    q => selectedAnswers.value[q.id] && !q.submitted
  )
  await Promise.all(pending.map(q => submitAnswer(q)))
  examSubmitted.value = true
}

async function loadWrongQuestions(): Promise<void> {
  loadingWrong.value = true
  try {
    const res = await api.get<WrongQuestion[]>('/quiz/wrong-questions')
    wrongQuestions.value = res.data
  } finally {
    loadingWrong.value = false
  }
}

function redoQuestion(q: WrongQuestion): void {
  quizStore.quizzes.push({
    id: q.id,
    question: q.question,
    question_type: q.question_type || 'choice',
    options: q.options || null,
    submitted: false,
    result: undefined
  })
  delete selectedAnswers.value[q.id]
  wrongQuestions.value = wrongQuestions.value.filter(w => w.id !== q.id)
}

onMounted(() => {
  documentStore.fetchDocuments()
})

onUnmounted(() => {
  ctx.revert()
})
</script>