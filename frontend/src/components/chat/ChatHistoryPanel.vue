<script setup lang="ts">
import { ref } from 'vue'
import { useChatStore } from '../../stores/chat'
import { ElMessage } from 'element-plus'
import { Close, EditPen, Search } from '@/components/icons'
import type { ChatSessionSummary } from '../../stores/chat'

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

const searchInput = ref('')
let searchTimer: ReturnType<typeof setTimeout> | null = null

// P2-1：formatDate 由 useFormat.formatRelativeTime 替换（原为平行实现之一）
const formatDate = (ts: string) => {
  if (!ts) return ''
  const d = new Date(ts)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins}分钟前`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}小时前`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}天前`
  return d.toLocaleDateString('zh-CN')
}

function onSearchInput() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    chatStore.searchMessages(searchInput.value || '')
  }, 300)
}

async function loadSession(sessionId: string) {
  chatStore.clearSearch()
  await chatStore.fetchHistory(sessionId)
  chatStore.currentSessionTitle =
    chatStore.sessions.find(s => s.session_id === sessionId)?.title || ''
  emit('loaded', sessionId)
}

function goToSession(sessionId: string) {
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
    ElMessage.success('对话已删除')
    emit('deleted', deleteModal.value.sessionId)
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
        aria-label="关闭历史记录"
        class="text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
        @click="emit('close')"
      >
        <el-icon class="w-5 h-5"><Close /></el-icon>
      </button>
    </div>

    <!-- Search Bar -->
    <div class="p-3 border-b border-[var(--border-default)]">
      <div class="relative">
        <el-icon class="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]">
          <Search />
        </el-icon>
        <input
          v-model="searchInput"
          @input="onSearchInput"
          @keydown.escape="chatStore.clearSearch(); searchInput = ''"
          placeholder="语义搜索历史对话..."
          class="w-full pl-9 pr-8 py-2 text-sm bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-md
                 text-[var(--text-primary)] placeholder:text-[var(--text-muted)]
                 focus:outline-none focus:border-[var(--color-primary)] transition-colors"
        />
        <button
          v-if="searchInput"
          @click="chatStore.clearSearch(); searchInput = ''"
          class="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
        >
          <el-icon class="w-3.5 h-3.5"><Close /></el-icon>
        </button>
      </div>
      <!-- Search Results -->
      <div v-if="chatStore.isSearching" class="mt-2 text-xs text-[var(--text-muted)] text-center py-2">
        搜索中...
      </div>
      <div v-else-if="chatStore.searchResults.length > 0" class="mt-2 space-y-1.5 max-h-64 overflow-y-auto">
        <div
          v-for="result in chatStore.searchResults"
          :key="result.message_id"
          @click="goToSession(result.session_id)"
          class="p-2 rounded-md bg-[var(--bg-secondary)] border border-[var(--border-default)] cursor-pointer
                 hover:border-[var(--color-primary)] transition-colors"
        >
          <div class="flex items-center justify-between gap-2">
            <span class="text-xs text-[var(--text-muted)] truncate">
              {{ result.session_id === chatStore.currentSession ? '当前会话' : result.session_id.slice(0, 8) }}
            </span>
            <span class="text-xs text-[var(--color-primary)] flex-shrink-0">
              {{ (result.similarity * 100).toFixed(0) }}%
            </span>
          </div>
          <div class="text-xs text-[var(--text-secondary)] mt-1 line-clamp-2">
            {{ result.role === 'user' ? '我: ' : 'AI: ' }}{{ result.content }}
          </div>
        </div>
      </div>
      <div v-else-if="chatStore.searchQuery && !chatStore.isSearching && chatStore.searchResults.length === 0"
           class="mt-2 text-xs text-[var(--text-muted)] text-center py-2">
        未找到相关对话
      </div>
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
                <!-- Edit Button（P3-3：触屏/md 悬停双态可见） -->
                <button
                  aria-label="重命名对话"
                  class="text-[var(--text-muted)] hover:text-[var(--color-primary)] opacity-100 md:opacity-0 md:group-hover:opacity-100 focus:opacity-100"
                  @click.stop="startEditTitle(session)"
                >
                  <el-icon class="w-4 h-4"><EditPen /></el-icon>
                </button>
              </div>
            </div>
          </div>
          <div class="text-xs text-[var(--text-muted)] mt-1">
            {{ formatDate(session.created_at || '') }}
          </div>
        </div>

        <!-- Delete Button（P3-3：触屏常显） -->
        <div class="px-3 pb-2 flex justify-end">
          <button
            aria-label="删除对话"
            class="text-xs text-[var(--color-error)] hover:opacity-80 opacity-100 md:opacity-0 md:group-hover:opacity-100 focus:opacity-100 transition-opacity"
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
      role="dialog"
      aria-modal="true"
      :aria-label="`确认删除对话: ${deleteModal.title}`"
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      @click.self="deleteModal.show = false"
      @keydown.escape="deleteModal.show = false"
    >
      <div class="bg-[var(--bg-secondary)] rounded-xl p-6 max-w-sm w-full mx-4" @click.stop>

        <h3 class="text-lg font-medium text-[var(--text-primary)] mb-4">确认删除</h3>
        <p class="text-sm text-[var(--text-secondary)] mb-6">确定要删除「{{ deleteModal.title }}」吗？此操作无法撤销。</p>
        <div class="flex gap-3 justify-end">
          <button
            class="px-4 py-2 text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            @click="deleteModal.show = false"
          >
            取消
          </button>
          <button
            class="px-4 py-2 bg-[var(--color-error)] text-[var(--text-inverse)] rounded-md hover:opacity-90"
            @click="deleteSession"
          >
            删除
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
