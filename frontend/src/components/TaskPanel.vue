<template>
  <div class="space-y-6">
    <!-- 顶栏标题与快捷操作 -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-[var(--border-default)]">
      <div>
        <h1 class="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-2.5">
          <el-icon class="w-6 h-6 text-[var(--color-primary)]"><TrendCharts /></el-icon>
          后台任务控制台
        </h1>
        <p class="text-sm text-[var(--text-muted)] mt-1">
          实时监控与追踪异步文档解析、向量索引构建及测验生成的执行状态
        </p>
      </div>
      <div class="flex items-center gap-3">
        <el-button
          size="default"
          :loading="isLoading"
          @click="fetchTasks"
        >
          <el-icon class="w-4 h-4 mr-1.5" :class="{ 'is-loading': isLoading }"><Loading /></el-icon>
          刷新数据
        </el-button>
        <el-button
          type="primary"
          size="default"
          @click="$router.push('/upload')"
        >
          <el-icon class="w-4 h-4 mr-1.5"><Upload /></el-icon>
          上传新文档
        </el-button>
      </div>
    </div>

    <!-- 任务统计卡片网格 -->
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
      <!-- 全部 -->
      <div
        @click="selectedStatus = 'all'"
        class="card p-4 cursor-pointer transition-all border hover:border-[var(--border-hover)]"
        :class="selectedStatus === 'all' ? 'border-[var(--color-primary)] ring-1 ring-[var(--color-primary)]' : 'border-[var(--border-default)]'"
      >
        <div class="text-xs text-[var(--text-muted)]">全部任务</div>
        <div class="text-2xl font-bold text-[var(--text-primary)] mt-1">{{ tasks.length }}</div>
      </div>
      <!-- 进行中 -->
      <div
        @click="selectedStatus = 'running'"
        class="card p-4 cursor-pointer transition-all border hover:border-[var(--border-hover)]"
        :class="selectedStatus === 'running' ? 'border-[var(--color-primary)] ring-1 ring-[var(--color-primary)]' : 'border-[var(--border-default)]'"
      >
        <div class="flex items-center justify-between">
          <span class="text-xs text-[var(--text-muted)]">进行中</span>
          <span v-if="runningCount > 0" class="w-2 h-2 rounded-full bg-[var(--color-info)] animate-ping"></span>
        </div>
        <div class="text-2xl font-bold text-[var(--color-info)] mt-1">{{ runningCount }}</div>
      </div>
      <!-- 已完成 -->
      <div
        @click="selectedStatus = 'completed'"
        class="card p-4 cursor-pointer transition-all border hover:border-[var(--border-hover)]"
        :class="selectedStatus === 'completed' ? 'border-[var(--color-primary)] ring-1 ring-[var(--color-primary)]' : 'border-[var(--border-default)]'"
      >
        <div class="text-xs text-[var(--text-muted)]">已完成</div>
        <div class="text-2xl font-bold text-[var(--color-success)] mt-1">{{ completedCount }}</div>
      </div>
      <!-- 失败/异常 -->
      <div
        @click="selectedStatus = 'failed'"
        class="card p-4 cursor-pointer transition-all border hover:border-[var(--border-hover)]"
        :class="selectedStatus === 'failed' ? 'border-[var(--color-primary)] ring-1 ring-[var(--color-primary)]' : 'border-[var(--border-default)]'"
      >
        <div class="text-xs text-[var(--text-muted)]">失败 / 异常</div>
        <div class="text-2xl font-bold text-[var(--color-error)] mt-1">{{ failedCount }}</div>
      </div>
    </div>

    <!-- 过滤与搜索工具栏 -->
    <div class="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-2">
      <!-- 状态筛选 Tab 胶囊 -->
      <div class="flex items-center gap-1.5 overflow-x-auto py-1">
        <button
          v-for="tab in statusTabs"
          :key="tab.value"
          @click="selectedStatus = tab.value"
          class="px-3 py-1.5 text-xs font-medium rounded-lg transition-all cursor-pointer whitespace-nowrap"
          :class="selectedStatus === tab.value
            ? 'bg-[var(--color-primary)] text-[var(--text-inverse)] font-semibold shadow-xs'
            : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] border border-[var(--border-default)]'"
        >
          {{ tab.label }}
          <span class="ml-1 opacity-75">({{ tab.count }})</span>
        </button>
      </div>

      <!-- 搜索输入框 -->
      <div class="w-full sm:w-80">
        <el-input
          v-model="searchKeyword"
          :prefix-icon="Search"
          clearable
          placeholder="搜索文件名、任务名称或任务 ID..."
          size="default"
        />
      </div>
    </div>

    <!-- 加载骨架屏 -->
    <SkeletonList v-if="isLoading && tasks.length === 0" variant="rows" :count="4" />

    <!-- 空状态 -->
    <EmptyState
      v-else-if="filteredTasks.length === 0"
      size="lg"
      :icon="Reading"
      :message="tasks.length === 0 ? '暂无后台任务' : '无匹配的任务记录'"
      :hint="tasks.length === 0 ? '上传文档或发起批量测验生成后，异步流水线将在此实时呈现执行进度与结果' : '可尝试清空搜索关键字或切换状态筛选标签'"
    >
      <el-button v-if="tasks.length === 0" type="primary" @click="$router.push('/upload')">去上传文档</el-button>
      <el-button v-else @click="resetFilters">重置筛选条件</el-button>
    </EmptyState>

    <!-- 任务卡片列表（破除 256px 矮盒限制，宽屏完整自然排布） -->
    <div v-else class="space-y-3.5">
      <div
        v-for="task in filteredTasks"
        :key="task.id"
        class="card p-4 sm:p-5 border transition-all hover:border-[var(--border-hover)] shadow-xs"
        :class="taskBorderClass(task)"
      >
        <!-- 第一行：状态图标 + 差异化任务标题 + 业务标签 + 操作按钮 -->
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div class="flex items-start sm:items-center gap-3 min-w-0">
            <!-- 状态图标 -->
            <div class="flex-shrink-0 mt-0.5 sm:mt-0">
              <el-icon v-if="task.status === 'running'" class="w-5 h-5 text-[var(--color-primary)] is-loading">
                <Loading />
              </el-icon>
              <el-icon v-else-if="task.status === 'completed'" class="w-5 h-5 text-[var(--color-success)]">
                <CircleCheckFilled />
              </el-icon>
              <el-icon v-else-if="task.status === 'failed'" class="w-5 h-5 text-[var(--color-error)]">
                <CircleCloseFilled />
              </el-icon>
              <el-icon v-else class="w-5 h-5 text-[var(--text-muted)]">
                <Clock />
              </el-icon>
            </div>

            <!-- 标题与业务标签 -->
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2">
                <!-- 突出且可区分的任务主标题 -->
                <h3 class="text-base font-semibold text-[var(--text-primary)] truncate" :title="getTaskInfo(task).title">
                  {{ getTaskInfo(task).title }}
                </h3>

                <!-- 任务类型徽章 -->
                <el-tag size="small" effect="plain" type="info" class="flex-shrink-0">
                  {{ getTaskInfo(task).taskBadge }}
                </el-tag>

                <!-- 任务简短 ID 徽章 -->
                <span class="text-[11px] font-mono text-[var(--text-muted)] bg-[var(--bg-tertiary)] px-1.5 py-0.5 rounded border border-[var(--border-default)]">
                  #{{ task.id.slice(0, 8) }}
                </span>
              </div>

              <!-- 动态副标题说明 -->
              <p class="text-xs text-[var(--text-secondary)] mt-1">
                {{ getTaskInfo(task).subtitle }}
              </p>
            </div>
          </div>

          <!-- 右侧状态标签与交互动作按钮 -->
          <div class="flex items-center gap-2.5 self-end sm:self-center flex-shrink-0">
            <!-- 状态标签 -->
            <el-tag
              size="small"
              :type="statusTagType(task)"
              effect="light"
            >
              {{ statusText(task) }}
            </el-tag>

            <!-- 取消进行中任务 -->
            <el-button
              v-if="task.status === 'pending' || task.status === 'running'"
              size="small"
              type="danger"
              plain
              @click="cancelTask(task.id)"
            >
              取消任务
            </el-button>

            <!-- 查看文档快捷跳转 -->
            <el-button
              v-if="task.status === 'completed' && getTaskInfo(task).targetDocId"
              size="small"
              type="default"
              plain
              @click="goToDocument(getTaskInfo(task).targetDocId!)"
            >
              查看文档
            </el-button>

            <!-- 前往测验快捷跳转 -->
            <el-button
              v-if="task.status === 'completed' && task.task_type === 'quiz_generate'"
              size="small"
              type="default"
              plain
              @click="$router.push('/quiz')"
            >
              前往测验
            </el-button>
          </div>
        </div>

        <!-- 运行中的进度条与当前阶段提示 -->
        <div v-if="task.status === 'running' || task.status === 'pending'" class="mt-3.5 pt-3 border-t border-[var(--border-default)]">
          <div class="flex items-center justify-between text-xs text-[var(--text-muted)] mb-1.5">
            <span>{{ runningPhaseText(task) }}</span>
            <span class="font-mono font-medium text-[var(--text-primary)]">{{ Math.round(task.progress * 100) }}%</span>
          </div>
          <el-progress
            :percentage="Math.round(task.progress * 100)"
            :stroke-width="6"
            :show-text="false"
          />
        </div>

        <!-- 详细指标行：耗时与时间戳 -->
        <div class="flex flex-wrap items-center justify-between gap-2 mt-3 pt-2 text-xs text-[var(--text-muted)] border-t border-[var(--border-default)]/60">
          <div class="flex flex-wrap items-center gap-3">
            <span v-if="getTaskInfo(task).durationText">
              执行耗时：<strong class="text-[var(--text-secondary)] font-medium">{{ getTaskInfo(task).durationText }}</strong>
            </span>
            <span v-if="getTaskInfo(task).chunkCount">
              切片规模：<strong class="text-[var(--text-secondary)] font-medium">{{ getTaskInfo(task).chunkCount }} 段</strong>
            </span>
            <span v-if="getTaskInfo(task).methodText">
              分块策略：<strong class="text-[var(--text-secondary)] font-medium">{{ getTaskInfo(task).methodText }}</strong>
            </span>
          </div>
          <div class="flex items-center gap-3 font-mono text-[11px]">
            <span>提交于 {{ formatTime(task.created_at) }}</span>
            <span v-if="task.completed_at">完成于 {{ formatTime(task.completed_at) }}</span>
          </div>
        </div>

        <!-- 失败错误详情气泡 -->
        <div v-if="task.status === 'failed' && task.error" class="mt-3 p-2.5 rounded-lg bg-[var(--color-error-light)] border border-[var(--color-error)]/20 text-xs text-[var(--color-error)] flex items-start gap-2">
          <el-icon class="w-4 h-4 flex-shrink-0 mt-0.5"><WarningFilled /></el-icon>
          <span class="leading-relaxed">{{ task.error }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import api from '../services/api'
import { useToastStore } from '../stores/toast'
import { useDocumentStore } from '../stores/document'
import { formatTime } from '../composables/useFormat'
import SkeletonList from './common/SkeletonList.vue'
import EmptyState from './common/EmptyState.vue'
import type { Task } from '../types/models'
import {
  TrendCharts, Upload, CircleCheckFilled, CircleCloseFilled,
  Clock, Loading, Search, Reading, WarningFilled
} from '@/components/icons'

const router = useRouter()
const toast = useToastStore()
const documentStore = useDocumentStore()

const tasks = ref<Task[]>([])
const isLoading = ref(false)
const selectedStatus = ref<string>('all')
const searchKeyword = ref<string>('')
let refreshTimer: ReturnType<typeof setInterval> | null = null

// 统计数量
const runningCount = computed(() => tasks.value.filter(t => t.status === 'running' || t.status === 'pending').length)
const completedCount = computed(() => tasks.value.filter(t => t.status === 'completed').length)
const failedCount = computed(() => tasks.value.filter(t => t.status === 'failed').length)
const cancelledCount = computed(() => tasks.value.filter(t => t.status === 'cancelled').length)

// 筛选 Tabs
const statusTabs = computed(() => [
  { label: '全部', value: 'all', count: tasks.value.length },
  { label: '进行中', value: 'running', count: runningCount.value },
  { label: '已完成', value: 'completed', count: completedCount.value },
  { label: '失败异常', value: 'failed', count: failedCount.value },
  { label: '已取消', value: 'cancelled', count: cancelledCount.value },
])

// 过滤后的任务流
const filteredTasks = computed(() => {
  return tasks.value.filter(task => {
    // 1. 状态匹配
    if (selectedStatus.value === 'running') {
      if (task.status !== 'running' && task.status !== 'pending') return false
    } else if (selectedStatus.value !== 'all' && task.status !== selectedStatus.value) {
      return false
    }

    // 2. 关键词匹配（文件名、标题、任务类型、任务ID）
    if (searchKeyword.value.trim()) {
      const q = searchKeyword.value.trim().toLowerCase()
      const info = getTaskInfo(task)
      const matchesTitle = info.title.toLowerCase().includes(q)
      const matchesSubtitle = info.subtitle.toLowerCase().includes(q)
      const matchesId = task.id.toLowerCase().includes(q)
      const matchesType = task.task_type.toLowerCase().includes(q)
      if (!matchesTitle && !matchesSubtitle && !matchesId && !matchesType) {
        return false
      }
    }

    return true
  })
})

function resetFilters(): void {
  selectedStatus.value = 'all'
  searchKeyword.value = ''
}

function taskBorderClass(task: Task): string {
  switch (task.status) {
    case 'running': return 'border-[var(--color-primary)]/40 bg-[var(--color-primary-light)]/20'
    case 'completed': return 'border-[var(--border-default)] hover:border-[var(--border-hover)]'
    case 'failed': return 'border-[var(--color-error)]/30 bg-[var(--color-error-light)]/15'
    case 'cancelled': return 'border-[var(--border-default)] opacity-70'
    default: return 'border-[var(--border-default)]'
  }
}

function statusTagType(task: Task): 'primary' | 'success' | 'danger' | 'info' | 'warning' {
  switch (task.status) {
    case 'running': return 'primary'
    case 'completed': return 'success'
    case 'failed': return 'danger'
    case 'cancelled': return 'info'
    default: return 'warning'
  }
}

function statusText(task: Task): string {
  switch (task.status) {
    case 'pending': return '排队中'
    case 'running': return `执行中 ${Math.round(task.progress * 100)}%`
    case 'completed': return '已完成'
    case 'failed': return '失败'
    case 'cancelled': return '已取消'
    default: return task.status
  }
}

function runningPhaseText(task: Task): string {
  if (task.status === 'pending') return '任务已入队，等待工作进程认领调度...'
  const p = Math.round(task.progress * 100)
  if (task.task_type === 'document_process') {
    if (p < 25) return '正在加载文档与解析文本结构...'
    if (p < 60) return '正在进行文本分块与元数据切片...'
    return '正在计算特征向量并构建向量索引...'
  }
  if (task.task_type === 'quiz_generate') {
    if (p < 50) return '正在提取文档考点并组织题干...'
    return '正在调用大模型生成单选与简答题目及答案解析...'
  }
  return `任务进行中 (${p}%)`
}

function formatDuration(startStr?: string | null, endStr?: string | null): string {
  if (!startStr || !endStr) return ''
  const start = new Date(startStr).getTime()
  const end = new Date(endStr).getTime()
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) return ''
  const diffSec = (end - start) / 1000
  if (diffSec < 60) return `${diffSec.toFixed(1)} 秒`
  const min = Math.floor(diffSec / 60)
  const sec = Math.round(diffSec % 60)
  return `${min}分${sec}秒`
}

interface TaskDisplayInfo {
  title: string
  subtitle: string
  taskBadge: string
  targetDocId?: string
  chunkCount?: number
  methodText?: string
  durationText?: string
}

function getTaskInfo(task: Task): TaskDisplayInfo {
  const res = task.result || {}
  const duration = formatDuration(task.created_at, task.completed_at)

  if (task.task_type === 'document_process') {
    const docId = (res.doc_id as string) || ''
    // 优先从 task.result.filename，其次从 documentStore 找对应文件名
    const cachedDoc = docId ? documentStore.documents.find(d => d.id === docId) : undefined
    const filename = (res.filename as string) || cachedDoc?.filename || ((cachedDoc as any)?.title) || (docId ? `文档 ${docId.slice(0, 8)}` : '本地文档')

    const chunkCount = typeof res.chunk_count === 'number'
      ? res.chunk_count
      : (typeof res.chunks === 'number' ? res.chunks : (cachedDoc?.chunk_count || undefined))
    const method = (res.chunk_strategy || res.method) as string
    const methodMap: Record<string, string> = {
      hierarchical: '层次结构分块',
      semantic: '语义分块',
      fixed: '定长分块',
      heading: '标题层级分块',
    }
    const methodText = method ? (methodMap[method] || method) : undefined

    let subtitle = ''
    if (task.status === 'completed') {
      subtitle = chunkCount ? `已完成解析与索引，共切分为 ${chunkCount} 个知识段落` : '文档已解析入库并完成向量化'
    } else if (task.status === 'running') {
      subtitle = '正在执行文档解析、知识分块与本地向量化构建...'
    } else if (task.status === 'failed') {
      subtitle = task.error || '文档解析处理异常中止'
    } else {
      subtitle = '等待后台 Worker 认领'
    }

    return {
      title: `《${filename}》· 文档解析与向量化`,
      subtitle,
      taskBadge: '文档处理',
      targetDocId: docId,
      chunkCount,
      methodText,
      durationText: duration
    }
  }

  if (task.task_type === 'quiz_generate') {
    const docNames = Array.isArray(res.document_names) && res.document_names.length > 0
      ? res.document_names.map((n: string) => `《${n}》`).join('、')
      : ''
    const quizCount = (res.quiz_count as number) || (res.choice_count as number) || 5

    return {
      title: docNames ? `${docNames}· 智能测验生成` : `AI 智能测验生成 (${quizCount} 题)`,
      subtitle: task.status === 'completed'
        ? `成功生成 ${quizCount} 道针对性测试题及解析`
        : '大模型正在提取关键考点并编写考题...',
      taskBadge: '测验生成',
      durationText: duration
    }
  }

  if (task.task_type === 'tts_generate') {
    return {
      title: 'Edge TTS 语音合成朗读',
      subtitle: task.status === 'completed' ? '音频切片已成功合成' : '正在合成高保真语音朗读音频...',
      taskBadge: '语音合成',
      durationText: duration
    }
  }

  return {
    title: `${task.task_type} 任务 (#${task.id.slice(0, 8)})`,
    subtitle: `状态：${statusText(task)}`,
    taskBadge: task.task_type,
    durationText: duration
  }
}

function goToDocument(docId: string): void {
  router.push({ path: '/document', query: { docId } })
}

async function fetchTasks(): Promise<void> {
  isLoading.value = true
  try {
    const resp = await api.get<{ tasks: Task[] }>('/tasks', { params: { limit: 50 } })
    const newTasks: Task[] = resp.data.tasks || []

    const oldTaskMap = new Map(tasks.value.map(t => [t.id, t.status]))
    for (const task of newTasks) {
      const oldStatus = oldTaskMap.get(task.id)
      if (oldStatus && oldStatus !== task.status) {
        const info = getTaskInfo(task)
        if (task.status === 'completed') {
          toast.success(`任务「${info.title}」已完成`)
        } else if (task.status === 'failed') {
          toast.error(`任务「${info.title}」执行失败`)
        }
      }
    }

    tasks.value = newTasks
  } catch {
    // Silently fail on refresh
  } finally {
    isLoading.value = false
  }
}

async function cancelTask(taskId: string): Promise<void> {
  try {
    await api.delete(`/tasks/${taskId}`)
    toast.show('任务已成功取消', 'info')
    await fetchTasks()
  } catch {
    toast.error('取消任务失败')
  }
}

function startAutoRefresh(): void {
  refreshTimer = setInterval(() => {
    if (runningCount.value > 0) {
      fetchTasks()
    }
  }, 3000)
}

onMounted(() => {
  fetchTasks()
  startAutoRefresh()
  if (documentStore.documents.length === 0) {
    documentStore.fetchDocuments()
  }
})

onBeforeUnmount(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})
</script>
