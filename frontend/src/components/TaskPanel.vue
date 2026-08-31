<template>
  <div v-if="tasks.length > 0" class="task-panel">
    <!-- Header -->
    <div class="flex items-center justify-between mb-3">
      <h3 class="text-sm font-medium text-[var(--text-secondary)] flex items-center gap-2">
        <svg class="w-4 h-4 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
        </svg>
        后台任务
        <span v-if="runningCount > 0" class="text-xs bg-indigo-100 text-indigo-700 px-1.5 py-0.5 rounded-full">
          {{ runningCount }} 运行中
        </span>
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
            <span v-if="task.status === 'running'" class="flex h-2 w-2">
              <span class="animate-ping absolute inline-flex h-2 w-2 rounded-full bg-indigo-400 opacity-75"></span>
              <span class="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
            </span>
            <span v-else-if="task.status === 'completed'" class="text-[var(--color-success)]">
              <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
              </svg>
            </span>
            <span v-else-if="task.status === 'failed'" class="text-[var(--color-error)]">
              <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
              </svg>
            </span>
            <span v-else class="text-[var(--text-muted)]">
              <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clip-rule="evenodd" />
              </svg>
            </span>

            <span class="font-medium text-[var(--text-primary)]">{{ taskTypeName(task.task_type) }}</span>
          </div>

          <!-- Cancel button for pending/running tasks -->
          <button
            v-if="task.status === 'pending' || task.status === 'running'"
            @click="cancelTask(task.id)"
            class="text-xs text-[var(--text-muted)] hover:text-red-500 transition-colors"
            title="取消任务"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Progress bar -->
        <div v-if="task.status === 'running' || task.status === 'pending'" class="w-full bg-[var(--bg-active)] rounded-full h-1.5 mb-1">
          <div
            class="bg-indigo-500 h-1.5 rounded-full transition-all duration-500"
            :style="{ width: (task.progress * 100) + '%' }"
          ></div>
        </div>

        <!-- Status text -->
        <div class="flex items-center justify-between">
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

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import api from '../services/api'
import { useToastStore } from '../stores/toast'

const toast = useToastStore()
const tasks = ref([])
let refreshTimer = null

const runningCount = computed(() => {
  return tasks.value.filter(t => t.status === 'running' || t.status === 'pending').length
})

const taskTypeNames = {
  'document_process': '文档处理',
  'quiz_generate': '生成测验',
  'tts_generate': '语音合成',
  'document_parse': '文档解析',
  'vector_index': '索引构建',
}

function taskTypeName(type) {
  return taskTypeNames[type] || type
}

function taskBorderClass(task) {
  switch (task.status) {
    case 'running': return 'border-[var(--color-primary)]/20 bg-[var(--color-primary-light)]'
    case 'completed': return 'border-[var(--color-success)]/20 bg-[var(--color-success-light)]'
    case 'failed': return 'border-[var(--color-error)]/20 bg-[var(--color-error-light)]'
    case 'cancelled': return 'border-[var(--border-default)] bg-[var(--bg-secondary)]/30'
    default: return 'border-[var(--border-default)]'
  }
}

 function statusTextClass(task) {
  switch (task.status) {
    case 'running': return 'text-[var(--color-primary)]'
    case 'completed': return 'text-[var(--color-success)]'
    case 'failed': return 'text-[var(--color-error)]'
    case 'cancelled': return 'text-[var(--text-muted)]'
    default: return 'text-[var(--text-muted)]'
  }
}

function statusText(task) {
  switch (task.status) {
    case 'pending': return '等待中...'
    case 'running': return `进行中 ${Math.round(task.progress * 100)}%`
    case 'completed': return '已完成'
    case 'failed': return '失败'
    case 'cancelled': return '已取消'
    default: return task.status
  }
}

function formatTime(timeStr) {
  if (!timeStr) return ''
  try {
    const d = new Date(timeStr)
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

async function fetchTasks() {
  try {
    const resp = await api.get('/tasks', { params: { limit: 20 } })
    const newTasks = resp.data.tasks || []

    // Check for newly completed tasks — show toast
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

async function cancelTask(taskId) {
  try {
    await api.delete(`/tasks/${taskId}`)
    toast.show('任务已取消', 'info')
    await fetchTasks()
  } catch {
    toast.error('取消任务失败')
  }
}

function startAutoRefresh() {
  // Refresh every 3 seconds when there are running tasks
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
