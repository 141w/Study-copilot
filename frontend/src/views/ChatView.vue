<template>
  <div class="flex h-[calc(100vh-4rem)]">
    <!-- Chat Area -->
    <div class="flex-1 flex flex-col">
      <!-- Top Bar -->
      <div class="border-b border-[var(--border-default)] px-6 py-3 bg-[var(--surface-card)] flex items-center justify-between">
        <div class="flex items-center gap-4">
          <h1 class="text-xl font-semibold text-[var(--text-primary)]">AI 问答</h1>
          <span v-if="chatStore.currentSession" class="text-sm text-[var(--text-muted)]">
            {{ chatStore.currentSessionTitle }}
          </span>
        </div>
        <div class="flex items-center gap-3">
          <!-- New Chat Button -->
          <button
            @click="newChat"
            class="flex items-center gap-2 px-4 py-2 bg-[var(--color-primary)] text-white rounded-lg hover:opacity-90 transition-opacity"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
            </svg>
            新建对话
          </button>

          <!-- Export Chat Button -->
          <button
            @click="exportChat"
            :disabled="chatStore.messages.length === 0"
            class="flex items-center gap-2 px-3 py-2 rounded-lg border border-[var(--border-default)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            导出对话
          </button>

          <!-- Toggle History Sidebar -->
          <button
            @click="showHistory = !showHistory"
            class="flex items-center gap-2 px-3 py-2 rounded-lg transition-colors"
            :class="showHistory ? 'bg-[var(--color-primary)] text-white' : 'border border-[var(--border-default)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]'"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {{ showHistory ? '隐藏记录' : '历史记录' }}
          </button>

          <router-link
            to="/model-config"
            class="text-sm text-[var(--text-muted)] hover:text-[var(--color-primary)]"
          >
            模型配置
          </router-link>
        </div>
      </div>

      <!-- Document Selector -->
      <div class="border-b border-[var(--border-default)] px-6 py-3 bg-[var(--bg-secondary)]">
        <div class="flex items-center gap-3 flex-wrap">
          <span class="text-sm text-[var(--text-muted)]">参考文档:</span>
          <label
            v-for="doc in documentStore.documents.filter(d => d.status === 'ready')"
            :key="doc.id"
            class="flex items-center gap-2 px-3 py-1.5 rounded-full text-sm cursor-pointer transition-colors"
            :class="selectedDocs.includes(doc.id) ? 'bg-[var(--color-primary)] text-white' : 'bg-[var(--surface-card)] border border-[var(--border-default)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]'"
          >
            <input
              type="checkbox"
              :value="doc.id"
              v-model="selectedDocs"
              class="hidden"
            />
            {{ doc.filename }}
          </label>
          <span v-if="documentStore.documents.filter(d => d.status === 'ready').length === 0" class="text-sm text-[var(--text-muted)]">
            暂无文档，请先上传
          </span>
        </div>
      </div>
      
      <!-- Messages Area -->
      <div ref="messagesRef" class="flex-1 overflow-y-auto p-6 bg-[var(--bg-secondary)]">
        <div v-if="chatStore.messages.length === 0" class="max-w-2xl mx-auto text-center py-16">
          <div class="w-20 h-20 mx-auto mb-6 bg-gradient-to-br from-[#ef2cc1] to-[#fc4c02] rounded-2xl flex items-center justify-center">
            <svg class="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          </div>
          <h2 class="text-2xl font-semibold text-[var(--text-primary)] mb-2">你好，我是 Study Copilot</h2>
          <p class="text-[var(--text-muted)] mb-6">基于你的文档知识库，我可以回答你的问题</p>
          <div class="flex flex-wrap justify-center gap-2 text-sm text-[var(--text-muted)]">
            <span class="px-3 py-1 bg-[var(--surface-card)] rounded-full">上传文档</span>
            <span class="px-3 py-1 bg-[var(--surface-card)] rounded-full">开始问答</span>
            <span class="px-3 py-1 bg-[var(--surface-card)] rounded-full">生成练习题</span>
          </div>
        </div>
        
        <div v-else class="max-w-3xl mx-auto space-y-6">
          <div
            v-for="(msg, idx) in chatStore.messages"
            :key="idx"
            class="flex gap-4"
            :class="msg.role === 'user' ? 'flex-row-reverse' : ''"
          >
            <!-- Avatar -->
            <div
              class="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center"
              :class="msg.role === 'user' ? 'bg-[var(--color-primary)] text-white' : 'bg-gradient-to-br from-[#ef2cc1] to-[#fc4c02] text-white'"
            >
              <svg v-if="msg.role === 'user'" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
              <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            </div>

            <!-- Message Content -->
            <div
              class="flex-1 px-4 py-3 rounded-2xl max-w-[80%]"
              :class="msg.role === 'user' ? 'bg-[var(--color-primary)] text-white' : 'bg-[var(--surface-card)] shadow-sm border border-[var(--border-default)] text-[var(--text-primary)]'"
            >
              <!-- 思考中状态 -->
              <div v-if="msg.role === 'assistant' && msg.isStreaming && !msg.content" class="flex items-center gap-2 text-[var(--text-muted)]">
                <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span>思考中...</span>
              </div>
              <div v-else class="prose prose-sm max-w-none" v-html="renderMarkdown(msg.content)"></div>
              
              <!-- Sources -->
              <div v-if="msg.sources && msg.sources.length > 0 && (!msg.isStreaming || msg.content)" class="mt-3 pt-3 border-t border-[var(--border-default)]">
                <div class="flex items-center gap-2 mb-2">
                  <div class="text-xs text-[var(--text-muted)]">
                    参考来源:
                    <span v-if="msg.used_source_indices && msg.used_source_indices.length > 0">
                      (引用了 {{ msg.used_source_indices.length }} 个)
                    </span>
                  </div>
                </div>
                <div class="flex flex-wrap gap-2">
                  <button
                    v-for="(source, sidx) in (msg.filtered_sources && msg.filtered_sources.length > 0 ? msg.filtered_sources : msg.sources)"
                    :key="sidx"
                    @click="scrollToSource(source.index)"
                    class="source-card-btn text-xs px-3 py-2 rounded-lg bg-[var(--bg-tertiary)] border border-[var(--border-default)] text-[var(--text-secondary)] hover:bg-[var(--color-primary)] hover:text-white hover:border-[var(--color-primary)] transition-all flex items-center gap-1.5"
                    :data-source-index="source.index"
                  >
                    <span class="w-5 h-5 rounded-full bg-[var(--color-primary)] text-white text-xs flex items-center justify-center">
                      {{ source.index }}
                    </span>
                    <span v-if="source.source" class="max-w-[100px] truncate">{{ source.source }}</span>
                    <span v-if="source.page" class="text-[var(--text-muted)]">P{{ source.page }}</span>
                  </button>
                </div>
              </div>
              
              <!-- Source Cards (collapsed, shown when clicked) -->
              <div v-if="msg.expandedSources" class="mt-3 grid grid-cols-1 gap-2">
                <div 
                  v-for="(source, sidx) in msg.sources" 
                  :key="sidx"
                  :id="`source-card-${source.index}`"
                  class="source-card p-3 bg-gray-50 rounded-lg border border-gray-200 text-sm"
                >
                  <div class="flex items-center gap-2 mb-1">
                    <span class="w-5 h-5 rounded-full bg-[#010120] text-white text-xs flex items-center justify-center">
                      {{ source.index }}
                    </span>
                    <span v-if="source.source" class="font-medium text-gray-800">{{ source.source }}</span>
                    <span v-if="source.page" class="text-xs text-gray-500">P{{ source.page }}</span>
                  </div>
                  <div class="text-xs text-gray-600 line-clamp-2">{{ source.text }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Input Area -->
      <div class="p-4 bg-[var(--surface-card)] border-t border-[var(--border-default)]">
        <div class="max-w-3xl mx-auto">
          <ChatInput
            @send="handleSend"
            @stop="handleStop"
            :loading="chatStore.isStreaming"
            :disabled="selectedDocs.length === 0"
            placeholder="输入问题，按 Enter 发送..."
          />
          <div v-if="selectedDocs.length === 0" class="text-center mt-2 text-xs text-[var(--text-muted)]">
            请先选择参考文档
          </div>
        </div>
      </div>
    </div>

    <!-- History Sidebar -->
    <div
      v-if="showHistory"
      class="w-80 border-l border-[var(--border-default)] bg-[var(--surface-card)] flex flex-col transition-all"
    >
      <!-- Sidebar Header -->
      <div class="p-4 border-b border-[var(--border-default)] flex items-center justify-between">
        <h2 class="font-medium text-[var(--text-primary)]">对话历史</h2>
        <button @click="showHistory = false" class="text-[var(--text-muted)] hover:text-[var(--text-secondary)]">
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
                    @click.stop="startEditTitle(session)"
                    class="text-[var(--text-muted)] hover:text-[var(--color-primary)] opacity-0 group-hover:opacity-100"
                  >
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 15.232l2.536 2.536m0-2.536l-2.536 2.536m2.536-2.536l-2.536 2.536m2.536 2.536l2.536 2.536M4 20h4l2-2-4-4-2 2z" />
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
              @click.stop="confirmDelete(session)"
              class="text-xs text-[var(--color-error)] hover:opacity-80 opacity-0 group-hover:opacity-100 transition-opacity"
            >
              删除
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Delete Confirm Modal -->
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
            @click="deleteModal.show = false"
            class="px-4 py-2 text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          >
            取消
          </button>
          <button
            @click="deleteSession"
            class="px-4 py-2 bg-[var(--color-error)] text-white rounded-lg hover:opacity-90"
          >
            删除
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { defineOptions } from 'vue'

defineOptions({ name: 'ChatView' })

import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useChatStore } from '../stores/chat'
import { useDocumentStore } from '../stores/document'
import ChatInput from '../components/chat/ChatInput.vue'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import gsap from 'gsap'

const chatStore = useChatStore()
const documentStore = useDocumentStore()
const selectedDocs = ref([])
const showHistory = ref(false)
const messagesRef = ref(null)
const route = useRoute()

// Edit state
const editingSessionId = ref(null)
const editingTitle = ref('')

// Delete modal
const deleteModal = ref({
  show: false,
  sessionId: '',
  title: ''
})

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  highlight: function (str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return '<pre class="hljs"><code>' +
               hljs.highlight(str, { language: lang, ignoreIllegals: true }).value +
               '</code></pre>'
      } catch (__) {}
    }
    return '<pre class="hljs"><code>' + md.utils.escapeHtml(str) + '</code></pre>'
  }
})

function renderMarkdown(text) {
  if (!text) return ''
  let rendered = md.render(text)
  rendered = rendered.replace(/\[来源(\d+)\]/g, (match, num) => {
    return `<sup class="source-badge" data-index="${num}">[${num}]</sup>`
  })
  return rendered
}

function scrollToSource(index) {
  const lastMsg = chatStore.messages[chatStore.messages.length - 1]
  if (lastMsg && lastMsg.role === 'assistant') {
    // 切换来源卡片展开状态
    const msgIndex = chatStore.messages.length - 1
    chatStore.messages[msgIndex].expandedSources = !chatStore.messages[msgIndex].expandedSources
    
    setTimeout(() => {
      // 滚动到对应的来源卡片
      const card = document.getElementById(`source-card-${index}`)
      if (card) {
        card.scrollIntoView({ behavior: 'smooth', block: 'center' })
        card.classList.add('ring-2', 'ring-[#010120]', 'bg-blue-50')
        setTimeout(() => card.classList.remove('ring-2', 'ring-[#010120]', 'bg-blue-50'), 3000)
      }
    }, 100)
  }
}

// 点击来源卡片跳转回正文引用位置
function scrollToReference(sourceIndex) {
  // 查找正文中对应的引用徽章
  const badges = document.querySelectorAll(`.source-badge[data-index="${sourceIndex}"]`)
  if (badges.length > 0) {
    badges[0].scrollIntoView({ behavior: 'smooth', block: 'center' })
    badges[0].classList.add('scale-125')
    setTimeout(() => badges[0].classList.remove('scale-125'), 3000)
  }
}

async function handleSend(content) {
  if (selectedDocs.value.length === 0) return
  // 使用流式接口
  await chatStore.askQuestionStream(content, selectedDocs.value)
  await nextTick()
  scrollToBottom()
}

function handleStop() {
  chatStore.cancelStream()
}

function exportChat() {
  if (chatStore.messages.length === 0) return

  const title = chatStore.currentSessionTitle || '对话'
  let md = `# ${title}\n\n`

  for (const msg of chatStore.messages) {
    if (msg.role === 'user') {
      md += `## 用户\n\n${msg.content}\n\n`
    } else if (msg.role === 'assistant') {
      md += `## AI\n\n${msg.content}\n\n`
      if (msg.sources && msg.sources.length > 0) {
        md += `## 参考来源\n\n`
        msg.sources.forEach((source, idx) => {
          const src = source.source || '未知来源'
          const page = source.page ? ` P${source.page}` : ''
          const text = source.text ? ` — ${source.text}` : ''
          md += `${idx + 1}. ${src}${page}${text}\n`
        })
        md += '\n'
      }
    }
  }

  const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  const date = new Date().toISOString().slice(0, 10)
  a.href = url
  a.download = `chat-${date}.md`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

function newChat() {
  chatStore.clearMessages()
  chatStore.currentSession = null
  chatStore.currentSessionTitle = ''
  showHistory.value = false
}

async function loadSession(sessionId) {
  await chatStore.fetchHistory(sessionId)
  chatStore.currentSessionTitle = chatStore.sessions.find(s => s.session_id === sessionId)?.title || ''
  await nextTick()
  scrollToBottom()
  showHistory.value = false
}

function scrollToBottom() {
  if (messagesRef.value) {
    const el = messagesRef.value
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100
    if (nearBottom) {
      el.scrollTop = el.scrollHeight
    }
  }
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now - date
  
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前'
  if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前'
  if (diff < 604800000) return Math.floor(diff / 86400000) + '天前'
  
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

function startEditTitle(session) {
  editingSessionId.value = session.session_id
  editingTitle.value = session.title || ''
}

async function saveTitle(sessionId) {
  if (editingSessionId.value !== sessionId) return
  
  const newTitle = editingTitle.value.trim()
  if (newTitle) {
    await chatStore.updateSessionTitle(sessionId, newTitle)
  }
  
  editingSessionId.value = null
  editingTitle.value = ''
}

function confirmDelete(session) {
  deleteModal.value = {
    show: true,
    sessionId: session.session_id,
    title: session.title || '新对话'
  }
}

async function deleteSession() {
  if (!deleteModal.value.sessionId) return
  
  try {
    await chatStore.deleteSession(deleteModal.value.sessionId)
    
    if (chatStore.currentSession === deleteModal.value.sessionId) {
      newChat()
    }
  } catch (error) {
    console.error('Delete failed:', error)
  }
  
  deleteModal.value.show = false
}

// GSAP animation context for cleanup
let gsapCtx

// Track previous message count to only animate on new messages (not streaming updates)
let prevMsgCount = 0

watch(() => chatStore.messages.length, (newLen) => {
  nextTick(() => {
    scrollToBottom()
    // Only animate when a new message is added (length increased), not during streaming
    if (newLen > prevMsgCount && prevMsgCount > 0) {
      const container = messagesRef.value
      if (container) {
        const msgRows = container.querySelectorAll('.flex.gap-4')
        const lastMsg = msgRows[msgRows.length - 1]
        if (lastMsg) {
          gsap.from(lastMsg, { y: 20, opacity: 0, duration: 0.4, ease: 'power2.out' })
        }
      }
    }
    prevMsgCount = newLen
  })
})

onMounted(async () => {
  await chatStore.fetchSessions()
  await documentStore.fetchDocuments()

  if (documentStore.documents.length > 0) {
    selectedDocs.value = documentStore.documents
      .filter(d => d.status === 'ready')
      .slice(0, 1)
      .map(d => d.id)
  }

  // 处理来自其他页面的上下文参数
  const contextQuery = route.query.context
  const docId = route.query.docId

  if (docId && !selectedDocs.value.includes(docId)) {
    selectedDocs.value = [docId]
  }

  if (contextQuery) {
    await handleSend(contextQuery)
  }

  // Animate the empty state icon
  gsapCtx = gsap.context(() => {
    const emptyIcon = messagesRef.value?.querySelector('.w-20.h-20')
    if (emptyIcon) {
      gsap.from(emptyIcon, { scale: 0.8, opacity: 0, duration: 0.5, ease: 'back.out(1.2)' })
    }
  }, messagesRef.value)
})

onUnmounted(() => {
  gsapCtx?.revert()
})
</script>

<style>
.prose pre.hljs {
  background: var(--bg-tertiary);
  padding: 1rem;
  border-radius: 0.5rem;
  overflow-x: auto;
  font-size: 0.875rem;
}
.prose code {
  background: var(--bg-tertiary);
  padding: 0.125rem 0.25rem;
  border-radius: 0.25rem;
  font-size: 0.875rem;
}
.prose pre code {
  background: transparent;
  padding: 0;
}
.prose .source-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.25rem;
  height: 1.25rem;
  padding: 0 0.25rem;
  margin-left: 0.125rem;
  margin-right: 0.125rem;
  font-size: 0.625rem;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, #ef2cc1 0%, #fc4c02 100%);
  border-radius: 9999px;
  cursor: pointer;
  vertical-align: super;
  transition: all 0.2s ease;
}
.prose .source-badge:hover {
  transform: scale(1.1);
  box-shadow: 0 2px 8px rgba(239, 44, 193, 0.4);
}
</style>