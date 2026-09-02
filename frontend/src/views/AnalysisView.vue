<template>
  <div ref="contentRef" class="max-w-4xl mx-auto px-6 py-8">
    <h1 class="text-2xl font-semibold text-[var(--text-primary)] mb-8">学习分析</h1>

    <!-- Tabs（P2-5：el-tabs 替换手写按钮） -->
    <el-tabs v-model="activeTab" class="mb-6">
      <el-tab-pane label="做题历史" name="history" />
      <el-tab-pane label="统计概览" name="stats" />
    </el-tabs>

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
          class="card p-4"
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
              class="flex items-start gap-3 p-3 bg-[var(--bg-secondary)] rounded-xl"
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
      <div class="card p-6 mb-8">
        <h2 class="font-semibold text-[var(--text-primary)] mb-4">整体掌握情况</h2>

        <div v-if="quizStore.knowledgeStats.total_quizzes === 0" class="text-center py-8">
          <el-icon class="w-16 h-16 mx-auto mb-4 text-[var(--text-muted)]"><TrendCharts /></el-icon>
          <p class="text-[var(--text-muted)] mb-4">暂无统计数据</p>
          <p class="text-sm text-[var(--text-muted)]">完成一些练习后，这里会显示你的学习分析</p>
          <el-button type="primary" @click="$router.push('/quiz')" class="mt-4">
            开始练习
          </el-button>
        </div>

        <div v-else class="grid grid-cols-3 gap-6">
          <div class="text-center">
            <!-- 精修（批次3）：tabular-nums 防统计数字宽度抖动 -->
            <div class="text-3xl font-semibold tabular-nums text-[var(--color-primary)]">{{ quizStore.knowledgeStats.total_quizzes }}</div>
            <div class="text-sm text-[var(--text-muted)] mt-1">总做题数</div>
          </div>

          <div class="text-center">
            <div class="text-3xl font-semibold tabular-nums text-[var(--color-success)]">{{ quizStore.knowledgeStats.correct_count }}</div>
            <div class="text-sm text-[var(--text-muted)] mt-1">正确数</div>
          </div>

          <div class="text-center">
            <div class="text-3xl font-semibold tabular-nums" :class="accuracyColor(quizStore.knowledgeStats.accuracy_rate)">
              {{ quizStore.knowledgeStats.accuracy_rate }}%
            </div>
            <div class="text-sm text-[var(--text-muted)] mt-1">正确率</div>
          </div>
        </div>

        <!-- Progress Bar -->
        <div v-if="quizStore.knowledgeStats.total_quizzes > 0" class="mt-6">
          <div class="h-2 bg-[var(--bg-tertiary)] rounded-full overflow-hidden">
            <div
              class="h-full bg-gradient-to-r from-[var(--color-brand-from)] to-[var(--color-brand-to)] transition-all duration-500"
              :style="{ width: `${quizStore.knowledgeStats.accuracy_rate}%` }"
            ></div>
          </div>
        </div>
      </div>

      <!-- Weak Areas -->
      <div class="card">
        <div class="p-4 border-b border-[var(--border-default)]">
          <h2 class="font-semibold text-[var(--text-primary)]">知识点掌握情况</h2>
        </div>

        <div class="p-6">
          <div v-if="quizStore.weakAreas.length === 0" class="text-center text-[var(--text-muted)] py-8">
            <svg class="w-12 h-12 mx-auto mb-3 text-[var(--text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p>暂无数据分析，请先完成一些练习</p>
          </div>

          <div v-else class="space-y-4">
            <div
              v-for="area in quizStore.weakAreas"
              :key="area.topic"
              class="p-4 rounded-xl border border-[var(--border-default)]"
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
        <el-button type="primary" :loading="quizStore.analyzing" @click="analyzeWeakness">
          {{ quizStore.analyzing ? '分析中...' : '重新分析错题' }}
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// defineOptions 是编译器宏，无需导入
defineOptions({ name: 'AnalysisView' })

import { ref, computed, onMounted, onActivated, onUnmounted } from 'vue'
import gsap from 'gsap'
import { useQuizStore } from '../stores/quiz'
import type { QuizHistoryItem } from '../stores/quiz'
import { TrendCharts } from '@element-plus/icons-vue'

// P1-5：数据源统一收敛到 quiz store（原直连 3 个 api.get，
// 且 quizStore.fetchQuizHistory 已存在却未使用）
const quizStore = useQuizStore()
const activeTab = ref<'history' | 'stats'>('history')
const contentRef = ref<HTMLElement | null>(null)
let ctx: gsap.Context | null = null

interface HistoryGroup {
  date: string
  items: QuizHistoryItem[]
  count: number
  correct_rate: number
}

// 做题历史：从 store 的 quizResults 分组计算（视图只负责展示）
const history = computed<HistoryGroup[]>(() => {
  const results = quizStore.quizResults || []
  const grouped: Record<string, { items: QuizHistoryItem[]; count: number; correct: number }> = {}
  for (const r of results) {
    const date = new Date(r.submitted_at).toLocaleDateString('zh-CN')
    if (!grouped[date]) {
      grouped[date] = { items: [], count: 0, correct: 0 }
    }
    grouped[date].items.push(r)
    grouped[date].count++
    if (r.is_correct) grouped[date].correct++
  }
  return Object.entries(grouped)
    .map(([date, data]) => ({
      date,
      items: data.items,
      count: data.count,
      correct_rate: Math.round((data.correct / data.count) * 100)
    }))
    .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
})

async function analyzeWeakness(): Promise<void> {
  try {
    await quizStore.analyzeWrongAnswers()
  } catch (error) {
    console.error('Failed to analyze:', error)
  }
}

function accuracyColor(rate: number): string {
  if (rate < 50) return 'text-[var(--color-error)]'
  if (rate < 70) return 'text-[var(--color-warning)]'
  return 'text-[var(--color-success)]'
}

onMounted(async () => {
  await refreshData()
  if (contentRef.value) {
    ctx = gsap.context(() => {
      gsap.from(contentRef.value!, { y: 20, opacity: 0, duration: 0.5, ease: 'power2.out' })
    }, contentRef.value)
  }
})

onActivated(async () => {
  await refreshData()
})

onUnmounted(() => {
  ctx?.revert()
})

async function refreshData(): Promise<void> {
  // 三个数据源完全独立，并行加载；各自内部 catch，不会互相影响
  await Promise.all([
    quizStore.fetchQuizHistory().catch(() => {}),
    quizStore.fetchKnowledgeStats().catch(() => {}),
    quizStore.analyzeWrongAnswers().catch(() => {})
  ])
}
</script>
