<template>
  <div ref="contentRef" class="max-w-4xl mx-auto px-6 py-8">
    <h1 class="text-2xl font-semibold text-[var(--text-primary)] mb-8">学习分析</h1>

    <!-- Tabs -->
    <div class="flex gap-4 mb-6 border-b border-[var(--border-default)]">
      <button
        @click="activeTab = 'history'"
        class="px-4 py-2 text-sm font-medium transition-all"
        :class="activeTab === 'history' ? 'text-[#010120] border-b-2 border-[#010120]' : 'text-[var(--text-muted)]'"
      >
        做题历史
      </button>
      <button
        @click="activeTab = 'stats'"
        class="px-4 py-2 text-sm font-medium transition-all"
        :class="activeTab === 'stats' ? 'text-[#010120] border-b-2 border-[#010120]' : 'text-[var(--text-muted)]'"
      >
        统计概览
      </button>
    </div>

    <!-- History Tab -->
    <div v-if="activeTab === 'history'">
      <div v-if="history.length === 0" class="text-center text-[var(--text-muted)] py-12">
        <svg class="w-16 h-16 mx-auto mb-4 text-[var(--text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
        </svg>
        <p class="text-[var(--text-muted)]">暂无做题记录</p>
      </div>

      <div v-else class="space-y-4">
        <div
          v-for="(group, idx) in history"
          :key="idx"
          class="el-card p-4"
        >
          <div class="flex items-center justify-between mb-3">
            <div>
              <span class="font-medium text-[var(--text-primary)]">{{ group.date }}</span>
              <span class="text-sm text-[var(--text-muted)] ml-3">
                {{ group.count }} 道题
              </span>
            </div>
            <span
              class="text-sm font-medium"
              :class="group.correct_rate >= 70 ? 'text-[var(--color-success)]' : group.correct_rate >= 40 ? 'text-[var(--color-warning)]' : 'text-[var(--color-error)]'"
            >
              正确率: {{ group.correct_rate }}%
            </span>
          </div>

          <div class="space-y-2">
            <div
              v-for="item in group.items"
              :key="item.quiz_id"
              class="flex items-start gap-3 p-3 bg-[var(--bg-secondary)] rounded-lg"
            >
              <span
                class="w-6 h-6 rounded-full text-xs flex items-center justify-center flex-shrink-0"
                :class="item.is_correct ? 'bg-[var(--color-success-light)] text-[var(--color-success)]' : 'bg-[var(--color-error-light)] text-[var(--color-error)]'"
              >
                {{ item.is_correct ? '✓' : '✗' }}
              </span>
              <div class="flex-1 min-w-0">
                <p class="text-sm text-[var(--text-primary)] truncate">{{ item.question }}</p>
                <div class="flex gap-4 mt-1 text-xs text-[var(--text-muted)]">
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
      <div class="el-card p-6 mb-8">
        <h2 class="font-semibold text-[var(--text-primary)] mb-4">整体掌握情况</h2>

        <div v-if="stats.total_quizzes === 0" class="text-center py-8">
          <el-icon class="w-16 h-16 mx-auto mb-4 text-[var(--text-muted)]"><TrendCharts /></el-icon>
          <p class="text-[var(--text-muted)] mb-4">暂无统计数据</p>
          <p class="text-sm text-[var(--text-muted)]">完成一些练习后，这里会显示你的学习分析</p>
          <button @click="$router.push('/quiz')" class="el-button-primary mt-4">
            开始练习
          </button>
        </div>

        <div v-else class="grid grid-cols-3 gap-6">
          <div class="text-center">
            <div class="text-3xl font-semibold text-[var(--color-primary)]">{{ stats.total_quizzes }}</div>
            <div class="text-sm text-[var(--text-muted)] mt-1">总做题数</div>
          </div>

          <div class="text-center">
            <div class="text-3xl font-semibold text-[var(--color-success)]">{{ stats.correct_count }}</div>
            <div class="text-sm text-[var(--text-muted)] mt-1">正确数</div>
          </div>

          <div class="text-center">
            <div class="text-3xl font-semibold" :class="accuracyColor(stats.accuracy_rate)">
              {{ stats.accuracy_rate }}%
            </div>
            <div class="text-sm text-[var(--text-muted)] mt-1">正确率</div>
          </div>
        </div>

        <!-- Progress Bar -->
        <div v-if="stats.total_quizzes > 0" class="mt-6">
          <div class="h-2 bg-[var(--bg-tertiary)] rounded-full overflow-hidden">
            <div
              class="h-full bg-gradient-to-r from-[#ef2cc1] to-[#fc4c02] transition-all duration-500"
              :style="{ width: `${stats.accuracy_rate}%` }"
            ></div>
          </div>
        </div>
      </div>

      <!-- Weak Areas -->
      <div class="el-card">
        <div class="p-4 border-b border-[var(--border-default)]">
          <h2 class="font-semibold text-[var(--text-primary)]">知识点掌握情况</h2>
        </div>

        <div class="p-6">
          <div v-if="weakAreas.length === 0" class="text-center text-[var(--text-muted)] py-8">
            <svg class="w-12 h-12 mx-auto mb-3 text-[var(--text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p>暂无数据分析，请先完成一些练习</p>
          </div>

          <div v-else class="space-y-4">
            <div
              v-for="area in weakAreas"
              :key="area.topic"
              class="p-4 rounded-lg border border-[var(--border-default)]"
            >
              <div class="flex items-center justify-between mb-3">
                <div>
                  <span class="font-medium text-[var(--text-primary)]">{{ area.topic }}</span>
                  <span class="text-sm text-[var(--text-muted)] ml-2">
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

              <div class="h-2 bg-[var(--bg-tertiary)] rounded-full overflow-hidden mb-3">
                <div
                  class="h-full transition-all duration-500"
                  :class="area.accuracy_rate < 50 ? 'bg-[var(--color-error)]' : area.accuracy_rate < 70 ? 'bg-[var(--color-warning)]' : 'bg-[var(--color-success)]'"
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
          class="el-button-primary"
        >
          {{ loading ? '分析中...' : '重新分析错题' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { defineOptions } from 'vue'

defineOptions({ name: 'AnalysisView' })

import { ref, onMounted, onActivated, onUnmounted } from 'vue'
import gsap from 'gsap'
import api from '../services/api'
import { useQuizStore } from '../stores/quiz'

const loading = ref(false)
const activeTab = ref('history')
const quizStore = useQuizStore()
const contentRef = ref(null)
let ctx = null
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
    const response = await api.get('/analysis/wrong')
    weakAreas.value = response.data.weak_areas || []
  } catch (error) {
    console.error('Failed to analyze:', error)
  } finally {
    loading.value = false
  }
}

function accuracyColor(rate) {
  if (rate < 50) return 'text-[var(--color-error)]'
  if (rate < 70) return 'text-[var(--color-warning)]'
  return 'text-[var(--color-success)]'
}

onMounted(async () => {
  await refreshData()
  // Entrance animation
  if (contentRef.value) {
    ctx = gsap.context(() => {
      gsap.from(contentRef.value, { y: 20, opacity: 0, duration: 0.5, ease: 'power2.out' })
    }, contentRef.value)
  }
})

onActivated(async () => {
  await refreshData()
})

onUnmounted(() => {
  ctx?.revert()
})

async function refreshData() {
  await Promise.all([
    quizStore.fetchQuizHistory(),
    loadHistory(),
    loadStats(),
    analyzeWeakness()
  ])
}
</script>