<template>
  <div v-if="tasks.length > 0" class="task-panel">
    <!-- Header -->
    <div class="flex items-center justify-between mb-3">
      <h3 class="text-sm font-medium text-[var(--text-secondary)] flex items-center gap-2">
        <el-icon class="w-4 h-4 text-[var(--color-info)]"><Document /></el-icon>
        后台任务
        <el-tag v-if="runningCount > 0" type="primary" size="small" effect="plain">
          {{ runningCount }} 运行中
        </el-tag>
      </h3>
    </div>

    <!-- Task list -->
    <div class="space-y-2 max-h-64 overflow-y-auto">
      <div
        v-for="task in tasks"
        :key="task.id"
        class="border rounded-lg p-3 text-sm transition-colors"
        :class="taskBorderClass(task)"
      >
        <!-- Task header -->
        <div class="flex items-center justify-between mb-1.5">
          <div class="flex items-center gap-2">
            <!-- Status icon -->
            <el-icon v-if="task.status === 'running'" class="w-4 h-4 text-[var(--color-info)] is-loading">
              <Loading />
            </el-icon>
            <el-icon v-else-if="task.status === 'completed'" class="w-4 h-4 text-[var(--color-success)]">
              <CircleCheckFilled />
            </el-icon>
            <el-icon v-else-if="task.status === 'failed'" class="w-4 h-4 text-[var(--color-error)]">
              <CircleCloseFilled />
            </el-icon>
            <el-icon v-else class="w-4 h-4 text-[var(--text-muted)]">
              <Clock />
            </el-icon>

            <span class="font-medium text-[var(--text-primary)]">{{ taskTypeName(task.task_type) }}</span>
          </div>

          <!-- Cancel button for pending/running tasks -->
          <el-button
            v-if="task.status === 'pending' || task.status === 'running'"
            link
            size="small"
            type="danger"
            @click="cancelTask(task.id)"
            title="取消任务"
          >
            <el-icon class="w-4 h-4"><Close /></el-icon>
          </el-button>
        </div>

        <!-- Progress bar -->
        <el-progress
          v-if="task.status === 'running' || task.status === 'pending'"
          :percentage="Math.round(task.progress * 100)"
          :stroke-width="6"
        />

        <!-- Status text -->
        <div class="flex items-center justify-between mt-1.5">
          <span class="text-xs" :class="statusTextClass(task)">
            {{ statusText(task) }}
          </span>
          <span class="text-xs text-[var(--text-muted)]">{{ formatTime(task.created_at) }}</span>
        </div>

        <!-- Error message -->
        <p v-if="task.status === 'failed' && task.error" class="text-xs text-[var(--color-error)] mt-1.5 truncate">
          {{ task.error }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import api from '../services/api'
import { useToastStore } from '../stores/toast'
import { formatTime } from '../composables/useFormat'
import type { Task } from '../types/models'
import {
  Document, CircleCheckFilled, CircleCloseFilled,
  Clock, Loading, Close
} from '@/components/icons'

const toast = useToastStore()
const tasks = ref<Task[]>([])
let refreshTimer: ReturnType<typeof setInterval> | null = null

const runningCount = computed(() => {
  return tasks.value.filter(t => t.status === 'running' || t.status === 'pending').length
})

const taskTypeNames: Record<string, string> = {
  'document_process': '文档处理',
  'quiz_generate': '生成测验',
  'tts_generate': '语音合成',
  'document_parse': '文档解析',
  'vector_index': '索引构建',
}

function taskTypeName(type: string): string {
  return taskTypeNames[type] || type
}

function taskBorderClass(task: Task): string {
  switch (task.status) {
    case 'running': return 'border-[var(--color-primary)]/20 bg-[var(--color-primary-light)]'
    case 'completed': return 'border-[var(--color-success)]/20 bg-[var(--color-success-light)]'
    case 'failed': return 'border-[var(--color-error)]/20 bg-[var(--color-error-light)]'
    case 'cancelled': return 'border-[var(--border-default)] bg-[var(--bg-secondary)]/30'
    default: return 'border-[var(--border-default)]'
  }
}

function statusTextClass(task: Task): string {
  switch (task.status) {
    case 'running': return 'text-[var(--color-primary)]'
    case 'completed': return 'text-[var(--color-success)]'
    case 'failed': return 'text-[var(--color-error)]'
    case 'cancelled': return 'text-[var(--text-muted)]'
    default: return 'text-[var(--text-muted)]'
  }
}

function statusText(task: Task): string {
  switch (task.status) {
    case 'pending': return '等待中...'
    case 'running': return `进行中 ${Math.round(task.progress * 100)}%`
    case 'completed': return '已完成'
    case 'failed': return '失败'
    case 'cancelled': return '已取消'
    default: return task.status
  }
}

// P2-1：formatTime 由 useFormat 提供（原为本地平行实现）

async function fetchTasks(): Promise<void> {
  try {
    const resp = await api.get<{ tasks: Task[] }>('/tasks', { params: { limit: 20 } })
    const newTasks: Task[] = resp.data.tasks || []

    const oldTaskMap = new Map(tasks.value.map(t => [t.id, t.status]))
    for (const task of newTasks) {
      const oldStatus = oldTaskMap.get(task.id)
      if (oldStatus && oldStatus !== task.status) {
        if (task.status === 'completed') {
          toast.success(`任务 "${taskTypeName(task.task_type)}" 已完成`)
        } else if (task.status === 'failed') {
          toast.error(`任务 "${taskTypeName(task.task_type)}" 失败`)
        }
      }
    }

    tasks.value = newTasks
  } catch {
    // Silently fail on refresh
  }
}

async function cancelTask(taskId: string): Promise<void> {
  try {
    await api.delete(`/tasks/${taskId}`)
    toast.show('任务已取消', 'info')
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
})

onBeforeUnmount(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})
</script>
