<template>
  <div class="max-w-4xl mx-auto px-6 py-8">
    <h1 class="text-2xl font-semibold text-gray-900 mb-8">学习分析</h1>

    <!-- Tabs -->
    <div class="flex gap-4 mb-6 border-b border-gray-200">
      <button
        @click="activeTab = 'history'"
        class="px-4 py-2 text-sm font-medium transition-all"
        :class="activeTab === 'history' ? 'text-[#010120] border-b-2 border-[#010120]' : 'text-gray-500'"
      >
        做题历史
      </button>
      <button
        @click="activeTab = 'stats'"
        class="px-4 py-2 text-sm font-medium transition-all"
        :class="activeTab === 'stats' ? 'text-[#010120] border-b-2 border-[#010120]' : 'text-gray-500'"
      >
        统计概览
      </button>
    </div>

    <!-- History Tab -->
    <div v-if="activeTab === 'history'">
      <div v-if="history.length === 0" class="text-center text-gray-400 py-12">
        <svg class="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
        </svg>
        <p class="text-gray-500">暂无做题记录</p>
      </div>

      <div v-else class="space-y-4">
        <div
          v-for="(group, idx) in history"
          :key="idx"
          class="card p-4"
        >
          <div class="flex items-center justify-between mb-3">
            <div>
              <span class="font-medium text-gray-900">{{ group.date }}</span>
              <span class="text-sm text-gray-500 ml-3">
                {{ group.count }} 道题
              </span>
            </div>
            <span
              class="text-sm font-medium"
              :class="group.correct_rate >= 70 ? 'text-green-500' : group.correct_rate >= 40 ? 'text-yellow-500' : 'text-red-500'"
            >
              正确率: {{ group.correct_rate }}%
            </span>
          </div>

          <div class="space-y-2">
            <div
              v-for="item in group.items"
              :key="item.quiz_id"
              class="flex items-start gap-3 p-3 bg-gray-50 rounded-lg"
            >
              <span
                class="w-6 h-6 rounded-full text-xs flex items-center justify-center flex-shrink-0"
                :class="item.is_correct ? 'bg-green-100 text-green-600' : 'bg-red-100 text-red-600'"
              >
                {{ item.is_correct ? '✓' : '✗' }}
              </span>
              <div class="flex-1 min-w-0">
                <p class="text-sm text-gray-900 truncate">{{ item.question }}</p>
                <div class="flex gap-4 mt-1 text-xs text-gray-500">
                  <span>你的答案: {{ item.user_answer }}</span>
                  <span v-if="!item.is_correct">正确答案: {{ item.correct_answer }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Stats Tab -->
    <div v-else>
      <!-- Knowledge Stats -->
      <div class="card p-6 mb-8">
        <h2 class="font-semibold text-gray-900 mb-4">整体掌握情况</h2>

        <div class="grid grid-cols-3 gap-6">
          <div class="text-center">
            <div class="text-3xl font-semibold text-[#010120]">{{ stats.total_quizzes }}</div>
            <div class="text-sm text-gray-500 mt-1">总做题数</div>
          </div>

          <div class="text-center">
            <div class="text-3xl font-semibold text-green-500">{{ stats.correct_count }}</div>
            <div class="text-sm text-gray-500 mt-1">正确数</div>
          </div>

          <div class="text-center">
            <div class="text-3xl font-semibold" :class="accuracyColor(stats.accuracy_rate)">
              {{ stats.accuracy_rate }}%
            </div>
            <div class="text-sm text-gray-500 mt-1">正确率</div>
          </div>
        </div>

        <!-- Progress Bar -->
        <div class="mt-6">
          <div class="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div
              class="h-full bg-gradient-to-r from-[#ef2cc1] to-[#fc4c02] transition-all duration-500"
              :style="{ width: `${stats.accuracy_rate}%` }"
            ></div>
          </div>
        </div>
      </div>

      <!-- Weak Areas -->
      <div class="card">
        <div class="p-4 border-b border-gray-100">
          <h2 class="font-semibold text-gray-900">知识点掌握情况</h2>
        </div>

        <div class="p-6">
          <div v-if="weakAreas.length === 0" class="text-center text-gray-400 py-8">
            <svg class="w-12 h-12 mx-auto mb-3 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p>暂无数据分析，请先完成一些练习</p>
          </div>

          <div v-else class="space-y-4">
            <div
              v-for="area in weakAreas"
              :key="area.topic"
              class="p-4 rounded-lg border border-gray-100"
            >
              <div class="flex items-center justify-between mb-3">
                <div>
                  <span class="font-medium text-gray-900">{{ area.topic }}</span>
                  <span class="text-sm text-gray-500 ml-2">
                    ({{ area.wrong_count }}/{{ area.total_count }} 错误)
                  </span>
                </div>
                <span
                  class="text-sm font-medium"
                  :class="accuracyColor(area.accuracy_rate)"
                >
                  {{ area.accuracy_rate }}%
                </span>
              </div>

              <div class="h-2 bg-gray-100 rounded-full overflow-hidden mb-3">
                <div
                  class="h-full transition-all duration-500"
                  :class="area.accuracy_rate < 50 ? 'bg-red-500' : area.accuracy_rate < 70 ? 'bg-yellow-500' : 'bg-green-500'"
                  :style="{ width: `${area.accuracy_rate}%` }"
                ></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Analyze Button -->
      <div class="mt-8 text-center">
        <button
          @click="analyzeWeakness"
          :disabled="loading"
          class="btn-primary"
        >
          {{ loading ? '分析中...' : '重新分析错题' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onActivated } from 'vue'
import api from '../services/api'
import { useQuizStore } from '../stores/quiz'

const loading = ref(false)
const activeTab = ref('history')
const quizStore = useQuizStore()
const stats = ref({
  total_quizzes: 0,
  correct_count: 0,
  accuracy_rate: 0
})
const weakAreas = ref([])
const history = ref([])

async function loadHistory() {
  try {
    const results = quizStore.quizResults || []

    if (results.length === 0) {
      history.value = []
      return
    }

    const grouped = {}
    for (const r of results) {
      const date = new Date(r.submitted_at).toLocaleDateString('zh-CN')
      if (!grouped[date]) {
        grouped[date] = {
          date,
          items: [],
          count: 0,
          correct: 0
        }
      }
      grouped[date].items.push(r)
      grouped[date].count++
      if (r.is_correct) grouped[date].correct++
    }

    history.value = Object.entries(grouped).map(([date, data]) => ({
      date,
      items: data.items,
      count: data.count,
      correct_rate: Math.round((data.correct / data.count) * 100)
    })).sort((a, b) => new Date(b.date) - new Date(a.date))
  } catch (error) {
    console.error('Failed to load history:', error)
  }
}

async function loadStats() {
  try {
    const response = await api.get('/analysis/knowledge')
    stats.value = response.data
  } catch (error) {
    console.error('Failed to load stats:', error)
  }
}

async function analyzeWeakness() {
  loading.value = true
  try {
    const response = await api.post('/analysis/wrong')
    weakAreas.value = response.data.weak_areas || []
  } catch (error) {
    console.error('Failed to analyze:', error)
  } finally {
    loading.value = false
  }
}

function accuracyColor(rate) {
  if (rate < 50) return 'text-red-500'
  if (rate < 70) return 'text-yellow-500'
  return 'text-green-500'
}

onMounted(async () => {
  await refreshData()
})

onActivated(async () => {
  await refreshData()
})

async function refreshData() {
  await quizStore.fetchQuizHistory()
  await loadHistory()
  await loadStats()
  await analyzeWeakness()
}
</script>