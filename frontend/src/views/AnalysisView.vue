<template>
  <div ref="contentRef" class="max-w-4xl mx-auto px-6 py-8">
    <h1 class="text-2xl font-semibold text-[var(--text-primary)] mb-8">学习分析</h1>

    <!-- Tabs（P2-5：el-tabs 替换手写按钮） -->
    <el-tabs v-model="activeTab" class="mb-6">
      <el-tab-pane label="做题历史" name="history" />
      <el-tab-pane label="统计概览" name="stats" />
      <el-tab-pane label="课堂学习" name="classroom" />
    </el-tabs>

    <!-- History Tab -->
    <div v-if="activeTab === 'history'">
      <!-- P1-2：首载骨架屏（匹配分组卡片形状），避免空态闪烁 -->
      <SkeletonList v-if="quizStore.loading && history.length === 0" variant="blocks" :count="2" />
      <div v-else-if="history.length === 0" class="text-center text-[var(--text-muted)] py-12">
        <el-icon class="w-16 h-16 mx-auto mb-4"><Document /></el-icon>
        <p class="text-[var(--text-muted)]">暂无做题记录</p>
        <p class="text-sm mt-1 text-[var(--text-muted)]">完成第一份练习后，这里会按日期汇总你的做题记录</p>
        <el-button type="primary" @click="$router.push('/quiz')" class="mt-4">开始练习</el-button>
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

        <!-- P3-8：移动端单列回退显式声明（§4.7） -->
        <div v-else class="grid grid-cols-1 sm:grid-cols-3 gap-6">
          <div class="text-center">
            <!-- 精修（批次3）：tabular-nums 防统计数字宽度抖动 -->
            <div class="text-3xl font-semibold tabular-nums text-[var(--color-primary)]">{{ quizStore.knowledgeStats.total_quizzes }}</div>
            <div class="text-sm text-[var(--text-muted)] mt-1">总做题数</div>
          </div>

          <div class="text-center">
            <div class="text-3xl font-semibold tabular-nums text-[var(--color-primary)]">{{ quizStore.knowledgeStats.correct_count }}</div>
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
            <!-- P5-4：进度条从 0 生长动画 -->
            <div
              class="h-full bg-gradient-to-r from-[var(--color-brand-from)] to-[var(--color-brand-to)] grow-bar"
              :style="{ '--target-w': `${quizStore.knowledgeStats.accuracy_rate}%` }"
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
            <el-icon class="w-12 h-12 mx-auto mb-3"><CircleCheck /></el-icon>
            <p>暂无数据分析，请先完成一些练习</p>
          </div>

          <div v-else class="space-y-4">
            <div
              v-for="area in quizStore.weakAreas"
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
                  class="h-full grow-bar"
                  :class="area.accuracy_rate < 50 ? 'bg-[var(--color-error)]' : area.accuracy_rate < 70 ? 'bg-[var(--color-warning)]' : 'bg-[var(--color-success)]'"
                  :style="{ '--target-w': `${area.accuracy_rate}%` }"
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

    <!-- Classroom Learning Tab（OpenMAIC 联动） -->
    <div v-if="activeTab === 'classroom'">
      <div v-if="classroomLoading" class="text-center py-12">
        <SkeletonList variant="blocks" :count="2" />
      </div>
      <div v-else-if="classrooms.length === 0" class="text-center py-12 text-[var(--text-muted)]">
        <el-icon class="w-16 h-16 mx-auto mb-4"><VideoPlay /></el-icon>
        <p>暂无课堂记录</p>
        <p class="text-xs mt-1">从课程或文档页面生成课堂后，这里会显示你的课堂视图</p>
        <el-button type="primary" plain @click="$router.push('/courses')" class="mt-4">去课程空间</el-button>
      </div>
      <div v-else class="space-y-4">
        <div
          v-for="c in classrooms"
          :key="c.course_id"
          class="card p-5 hover:border-[var(--border-hover)] transition-colors"
        >
          <div class="flex items-start gap-4">
            <div class="w-12 h-12 rounded-xl bg-[var(--color-primary-light)] flex items-center justify-center flex-shrink-0">
              <el-icon class="text-[var(--color-primary)] text-xl"><VideoPlay /></el-icon>
            </div>
            <div class="flex-1 min-w-0">
              <h3 class="font-medium text-[var(--text-primary)]">{{ c.title }}</h3>
              <p class="text-xs text-[var(--text-muted)] mt-1">{{ formatDate(c.created_at) }}</p>
              <div class="flex gap-2 mt-3">
                <el-button v-if="c.url" size="small" type="primary" @click="openUrl(c.url)">
                  进入课堂
                </el-button>
                <el-button v-if="c.url" size="small" @click="copyUrl(c.url)">
                  复制链接
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// defineOptions 是编译器宏，无需导入
defineOptions({ name: 'AnalysisView' })

import { ref, computed, onMounted, onActivated, onUnmounted, watch } from 'vue'
import gsap from 'gsap'
import { useQuizStore } from '../stores/quiz'
import type { QuizHistoryItem } from '../stores/quiz'
import { useOpenMAICStore } from '../stores/openmaic'
import { TrendCharts, Document, CircleCheck, VideoPlay } from '@/components/icons'
import SkeletonList from '../components/common/SkeletonList.vue'
import { useReducedMotion } from '../composables/useReducedMotion'
import { useToastStore } from '../stores/toast'

const toast = useToastStore()
const openmaic = useOpenMAICStore()

// P1-5：数据源统一收敛到 quiz store（原直连 3 个 api.get，
// 且 quizStore.fetchQuizHistory 已存在却未使用）
const quizStore = useQuizStore()
// P1-1：GSAP 动画降级（prefers-reduced-motion）
const { prefersReduced } = useReducedMotion()
const activeTab = ref<'history' | 'stats' | 'classroom'>('history')
const contentRef = ref<HTMLElement | null>(null)

// OpenMAIC 课堂数据（通过 store 管理）
const classroomLoading = computed(() => openmaic.loading)
const classrooms = computed(() => openmaic.classrooms)
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

// ── OpenMAIC 课堂数据 ─────────────────────────────────────────────────────────

async function loadClassrooms(): Promise<void> {
  await openmaic.fetchClassrooms()
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('zh-CN', {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
    })
  }
  catch {
    return iso
  }
}

function openUrl(url: string): void {
  window.open(url, '_blank')
}

async function copyUrl(url: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(url)
    toast.success('链接已复制')
  }
  catch {
    toast.error('复制失败')
  }
}

// 监听 tab 切换：进入课堂学习时自动加载
watch(activeTab, (tab) => {
  if (tab === 'classroom' && classrooms.value.length === 0 && !classroomLoading.value) {
    loadClassrooms()
  }
})

onMounted(async () => {
  await refreshData()
  // P1-1：减少动态偏好下跳过入场动画
  if (prefersReduced.value || !contentRef.value) return
  ctx = gsap.context(() => {
    gsap.from(contentRef.value!, { y: 20, opacity: 0, duration: 0.5, ease: 'power2.out' })
  }, contentRef.value)
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

<style scoped>
/* P5-4：进度条从 0 生长（0.8s ease-out；数据加载完成即播一次，不循环） */
.grow-bar {
  width: 0;
  animation: grow-to-target 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}
@keyframes grow-to-target {
  to { width: var(--target-w, 0%); }
}
/* §6.B：减少动态偏好下直接到位 */
@media (prefers-reduced-motion: reduce) {
  .grow-bar {
    animation: none;
    width: var(--target-w, 0%);
  }
}
</style>
