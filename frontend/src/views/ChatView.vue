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
            <IconPlus class="w-4 h-4" />
            新建对话
          </button>

          <!-- Export Chat Button -->
          <button
            @click="exportChat"
            :disabled="chatStore.messages.length === 0"
            class="flex items-center gap-2 px-3 py-2 rounded-lg border border-[var(--border-default)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <IconDownload class="w-4 h-4" />
            导出对话
          </button>

          <!-- Toggle History Sidebar -->
          <button
            @click="showHistory = !showHistory"
            class="flex items-center gap-2 px-3 py-2 rounded-lg transition-colors"
            :class="showHistory ? 'bg-[var(--color-primary)] text-white' : 'border border-[var(--border-default)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]'"
          >
            <IconClock class="w-4 h-4" />
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
            v-for="doc in readyDocs"
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
          <span v-if="!readyDocs.length" class="text-sm text-[var(--text-muted)]">
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
              <div v-else class="prose prose-sm max-w-none" v-html="renderMarkdown(msg.content, msg.isStreaming)"></div>

              <!-- 消息操作栏：朗读 + 复制（仅助手消息、非流式中、有内容时显示） -->
              <div
                v-if="msg.role === 'assistant' && !msg.isStreaming && msg.content"
                class="flex items-center gap-3 mt-2 pt-2 border-t border-[var(--border-default)]"
              >
                <TTSPlayer :text="msg.content" />
                <button
                  @click="copyMessage(msg)"
                  class="inline-flex items-center gap-1.5 px-2 py-1 text-xs rounded-md text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition-colors"
                  title="复制回答"
                >
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                  <span>{{ copiedMsgId === msg.id ? '已复制' : '复制' }}</span>
                </button>
              </div>

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
                  class="source-card p-3 bg-[var(--bg-secondary)] rounded-lg border border-[var(--border-default)] text-sm"
                >
                  <div class="flex items-center gap-2 mb-1">
                    <span class="w-5 h-5 rounded-full bg-[#010120] text-white text-xs flex items-center justify-center">
                      {{ source.index }}
                    </span>
                    <span v-if="source.source" class="font-medium text-[var(--text-primary)]">{{ source.source }}</span>
                    <span v-if="source.page" class="text-xs text-[var(--text-muted)]">P{{ source.page }}</span>
                  </div>
                  <div class="text-xs text-[var(--text-secondary)] line-clamp-2">{{ source.text }}</div>
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

    <!-- History Sidebar（会话列表/重命名/删除确认，自包含子组件） -->
    <ChatHistoryPanel
      :visible="showHistory"
      @close="showHistory = false"
      @loaded="onSessionLoaded"
      @deleted="onSessionDeleted"
    />
  </div>
</template>

<script setup>
import { defineOptions } from 'vue'

defineOptions({ name: 'ChatView' })

import { computed, ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useChatStore } from '../stores/chat'
import { useDocumentStore } from '../stores/document'
import ChatInput from '../components/chat/ChatInput.vue'
import ChatHistoryPanel from '../components/chat/ChatHistoryPanel.vue'
import { buildChatMarkdown, downloadChatMarkdown } from '../composables/useChatExport'
import TTSPlayer from '../components/TTSPlayer.vue'
import { useMarkdown } from '../composables/useMarkdown'
import gsap from 'gsap'
import IconPlus from '../components/common/icons/IconPlus.vue'
import IconDownload from '../components/common/icons/IconDownload.vue'
import IconClock from '../components/common/icons/IconClock.vue'

const chatStore = useChatStore()
const documentStore = useDocumentStore()
const readyDocs = computed(() => documentStore.readyDocuments)
const selectedDocs = ref([])
const showHistory = ref(false)
const messagesRef = ref(null)
const route = useRoute()

// 复制消息状态
const copiedMsgId = ref(null)

async function copyMessage(msg) {
  try {
    await navigator.clipboard.writeText(msg.content)
    copiedMsgId.value = msg.id
    setTimeout(() => { copiedMsgId.value = null }, 2000)
  } catch (e) {
    console.error('Copy failed:', e)
  }
}

const { renderMarkdown: renderMarkdownBase } = useMarkdown()

// Memoize markdown renders: key = content text, value = rendered HTML.
// Streaming messages (isStreaming=true) bypass cache and render as plain text.
const _mdCache = new Map()

function renderMarkdown(text, isStreaming = false) {
  if (!text) return ''
  if (isStreaming) return text.replace(/</g, '&lt;').replace(/\n/g, '<br>')
  const cached = _mdCache.get(text)
  if (cached) return cached
  let rendered = renderMarkdownBase(text)
  rendered = rendered.replace(/\[来源(\d+)\]/g, (match, num) => {
    return `<sup class="source-badge" data-index="${num}">[${num}]</sup>`
  })
  _mdCache.set(text, rendered)
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
  const md = buildChatMarkdown(chatStore.messages, chatStore.currentSessionTitle || '对话')
  downloadChatMarkdown(md)
}

function newChat() {
  chatStore.clearMessages()
  chatStore.currentSession = null
  chatStore.currentSessionTitle = ''
  showHistory.value = false
}

function onSessionLoaded(sessionId) {
  // 面板已完成 fetchHistory 与标题恢复；父级负责滚动与收起
  void sessionId
  nextTick(() => scrollToBottom())
  showHistory.value = false
}

function onSessionDeleted(sessionId) {
  // 删除的是当前会话时重置视图
  if (chatStore.currentSession === sessionId) {
    newChat()
  }
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