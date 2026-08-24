<script setup lang="ts">
import { ref } from 'vue'
import { useChatStore } from '../../stores/chat'
import type { ChatSessionSummary } from '../../stores/chat'

/**
 * 对话历史侧边栏（含会话重命名、删除确认弹窗）。
 * 自包含：会话数据直接读 chat store；通过事件向父级通知
 * 「已加载某会话」与「已删除当前会话」，滚动/收起等副作用由父级处理。
 */
const props = defineProps<{ visible: boolean }>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'loaded', sessionId: string): void
  (e: 'deleted', sessionId: string): void
}>()

const chatStore = useChatStore()

const editingSessionId = ref<string | null>(null)
const editingTitle = ref('')

const deleteModal = ref({
  show: false,
  sessionId: '',
  title: '',
})

function formatDate(dateStr?: string): string {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()

  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前'
  if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前'
  if (diff < 604800000) return Math.floor(diff / 86400000) + '天前'

  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

async function loadSession(sessionId: string) {
  await chatStore.fetchHistory(sessionId)
  chatStore.currentSessionTitle =
    chatStore.sessions.find(s => s.session_id === sessionId)?.title || ''
  emit('loaded', sessionId)
}

function startEditTitle(session: ChatSessionSummary) {
  editingSessionId.value = session.session_id
  editingTitle.value = session.title || ''
}

async function saveTitle(sessionId?: string) {
  if (!sessionId || editingSessionId.value !== sessionId) return

  const newTitle = editingTitle.value.trim()
  if (newTitle) {
    await chatStore.updateSessionTitle(sessionId, newTitle)
  }

  editingSessionId.value = null
  editingTitle.value = ''
}

function confirmDelete(session: ChatSessionSummary) {
  deleteModal.value = {
    show: true,
    sessionId: session.session_id,
    title: session.title || '新对话',
  }
}

async function deleteSession() {
  if (!deleteModal.value.sessionId) return

  try {
    await chatStore.deleteSession(deleteModal.value.sessionId)
    const removedId = deleteModal.value.sessionId
    emit('deleted', removedId)
  } catch (error) {
    console.error('Delete failed:', error)
  }

  deleteModal.value.show = false
}
</script>

<template>
  <!-- History Sidebar -->
  <div
    v-if="props.visible"
    class="w-80 border-l border-[var(--border-default)] bg-[var(--surface-card)] flex flex-col transition-all"
  >
    <!-- Sidebar Header -->
    <div class="p-4 border-b border-[var(--border-default)] flex items-center justify-between">
      <h2 class="font-medium text-[var(--text-primary)]">对话历史</h2>
      <button
        class="text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
        @click="emit('close')"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>

    <!-- Session List -->
    <div class="flex-1 overflow-y-auto">
      <div v-if="chatStore.sessions.length === 0" class="p-4 text-center text-[var(--text-muted)] text-sm">
        暂无历史对话
      </div>
      <div
        v-else
        v-for="session in chatStore.sessions"
        :key="session.session_id"
        class="border-b border-[var(--border-default)] hover:bg-[var(--bg-hover)] group"
        :class="{ 'bg-[var(--bg-hover)]': session.session_id === chatStore.currentSession }"
      >
        <!-- Session Item -->
        <div
          class="p-3 cursor-pointer"
          @click="loadSession(session.session_id)"
        >
          <div class="flex items-start justify-between gap-2">
            <div class="flex-1 min-w-0">
              <!-- Editing Title -->
              <div v-if="editingSessionId === session.session_id" class="flex items-center gap-2">
                <input
                  v-model="editingTitle"
                  @keyup.enter="saveTitle(session.session_id)"
                  @blur="saveTitle(session.session_id)"
                  class="flex-1 px-2 py-1 text-sm border border-[var(--border-focus)] rounded focus:outline-none bg-[var(--bg-primary)] text-[var(--text-primary)]"
                  @click.stop
                />
              </div>
              <div v-else class="flex items-center gap-2">
                <span class="text-sm text-[var(--text-secondary)] truncate block flex-1">
                  {{ session.title || '新对话' }}
                </span>
                <!-- Edit Button -->
                <button
                  class="text-[var(--text-muted)] hover:text-[var(--color-primary)] opacity-0 group-hover:opacity-100"
                  @click.stop="startEditTitle(session)"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 15.232l2.536 2.536m0-2.536l-2.536 2.536m2.536-2.536l-2.536 2.536m2.536-2.536l2.536 2.536M4 20h4l2-2-4-4-2 2z" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
          <div class="text-xs text-[var(--text-muted)] mt-1">
            {{ formatDate(session.created_at) }}
          </div>
        </div>

        <!-- Delete Button (hover show) -->
        <div class="px-3 pb-2 flex justify-end">
          <button
            class="text-xs text-[var(--color-error)] hover:opacity-80 opacity-0 group-hover:opacity-100 transition-opacity"
            @click.stop="confirmDelete(session)"
          >
            删除
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- Delete Confirm Modal -->
  <Teleport to="body">
    <div
      v-if="deleteModal.show"
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      @click="deleteModal.show = false"
    >
      <div class="bg-[var(--surface-card)] rounded-lg p-6 max-w-sm w-full mx-4" @click.stop>
        <h3 class="text-lg font-medium text-[var(--text-primary)] mb-4">确认删除</h3>
        <p class="text-[var(--text-secondary)] mb-6">确定要删除「{{ deleteModal.title }}」吗？此操作无法撤销。</p>
        <div class="flex gap-3 justify-end">
          <button
            class="px-4 py-2 text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            @click="deleteModal.show = false"
          >
            取消
          </button>
          <button
            class="px-4 py-2 bg-[var(--color-error)] text-white rounded-lg hover:opacity-90"
            @click="deleteSession"
          >
            删除
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
