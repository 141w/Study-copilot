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
          <el-button type="primary" :icon="Plus" @click="newChat">新建对话</el-button>
          <el-button :icon="Download" :disabled="chatStore.messages.length === 0" @click="exportChat">
            导出对话
          </el-button>
          <el-button :type="showHistory ? 'primary' : 'default'" :icon="Clock" @click="showHistory = !showHistory">
            {{ showHistory ? '隐藏记录' : '历史记录' }}
          </el-button>
          <router-link to="/model-config" class="text-sm text-[var(--text-muted)] hover:text-[var(--color-primary)]">
            模型配置
          </router-link>
        </div>
      </div>

      <!-- Document Selector -->
      <div class="border-b border-[var(--border-default)] px-6 py-3 bg-[var(--bg-secondary)]">
        <DocumentPicker v-model="selectedDocs" mode="multiple" label="参考文档" :documents="readyDocs" />
      </div>

      <!-- Messages Area -->
      <div ref="messagesRef" class="flex-1 overflow-y-auto p-6 bg-[var(--bg-secondary)]">
        <div v-if="chatStore.messages.length === 0" class="max-w-2xl mx-auto text-center py-16">
          <CopilotBotAvatar :size="120" mood="idle" />
          <h2 class="text-2xl font-semibold text-[var(--text-primary)] mb-2">你好，我是 Study Copilot</h2>
          <p class="text-[var(--text-muted)] mb-6">基于你的文档知识库，我可以回答你的问题</p>
          <div class="flex flex-wrap justify-center gap-2 text-sm text-[var(--text-muted)]">
            <span class="px-3 py-1 bg-[var(--surface-card)] rounded-full">上传文档</span>
            <span class="px-3 py-1 bg-[var(--surface-card)] rounded-full">开始问答</span>
            <span class="px-3 py-1 bg-[var(--surface-card)] rounded-full">生成练习题</span>
          </div>
        </div>

        <div v-else class="max-w-3xl mx-auto space-y-5">
          <div
            v-for="(msg, idx) in chatStore.messages"
            :key="idx"
            class="flex gap-3"
            :class="msg.role === 'user' ? 'flex-row-reverse' : ''"
          >
            <!-- Avatar -->
            <div class="flex-shrink-0 mt-0.5">
              <CopilotBotAvatar
                v-if="msg.role === 'assistant'"
                :is-streaming="msg.isStreaming"
                :size="40"
                :mood="msg === chatStore.messages[chatStore.messages.length - 1] ? botMood : 'idle'"
              />
              <div
                v-else
                class="w-10 h-10 rounded-full flex-shrink-0 flex items-center justify-center bg-[var(--color-primary)] text-white"
              >
                <el-icon class="w-5 h-5"><User /></el-icon>
              </div>
            </div>

            <!-- Message Content -->
            <div class="flex-1 max-w-[82%] min-w-0">

              <!-- User bubble -->
              <div
                v-if="msg.role === 'user'"
                class="px-4 py-2.5 rounded-2xl rounded-tr-sm bg-[var(--color-primary)] text-white text-[0.9rem] leading-relaxed inline-block max-w-full break-words"
                v-html="renderMarkdown(msg.content, false)"
              ></div>

              <!-- Assistant card -->
              <div
                v-else
                class="bg-[var(--surface-card)] border border-[var(--border-default)] rounded-2xl rounded-tl-sm shadow-sm overflow-hidden"
              >
                <!-- Thinking indicator -->
                <div v-if="msg.isStreaming && !msg.content"
                     class="px-4 py-2.5 flex items-center gap-2 text-[var(--text-muted)] text-sm">
                  <el-icon class="w-4 h-4 is-loading"><RefreshRight /></el-icon>
                  <span>思考中...</span>
                </div>

                <template v-else>
                  <!-- Thinking steps -->
                  <details
                    v-if="Array.isArray(msg.thinking) && msg.thinking.length > 0"
                    class="thinking-section"
                  >
                    <summary class="thinking-summary text-xs text-[var(--text-muted)] cursor-pointer select-none flex items-center gap-1.5 list-none py-2 px-4 hover:text-[var(--text-secondary)]">
                      <el-icon class="w-3.5 h-3.5 transition-transform duration-200">
                        <ArrowRight />
                      </el-icon>
                      思考过程 ({{ msg.thinking.length }} 步)
                    </summary>
                    <div v-for="(t, ti) in msg.thinking" :key="ti"
                         class="flex items-start gap-2 px-4 pb-2 text-xs text-[var(--text-muted)]">
                      <span class="font-medium text-[var(--color-accent)] flex-shrink-0">{{ String(t.step) }}.</span>
                      <span class="leading-relaxed">{{ t.detail }}</span>
                    </div>
                  </details>

                  <!-- Answer -->
                  <div class="px-4 py-3 text-[0.9rem] leading-[1.7] text-[var(--text-primary)] prose prose-sm max-w-none">
                    <div v-html="renderMarkdown(msg.content, msg.isStreaming)"></div>
                  </div>

                  <!-- Actions -->
                  <div
                    v-if="!msg.isStreaming && msg.content"
                    class="flex items-center gap-1 px-4 py-1.5 border-t border-[var(--border-default)]"
                  >
                    <TTSPlayer :text="msg.content" />
                    <el-button size="small" text bg @click="copyMessage(msg)" title="复制回答">
                      <el-icon class="w-3.5 h-3.5 mr-1"><DocumentCopy /></el-icon>
                      {{ copiedMsgId === msg.id ? '已复制' : '复制' }}
                    </el-button>
                  </div>

                  <!-- Sources -->
                  <div v-if="msg.sources && msg.sources.length > 0 && (!msg.isStreaming || msg.content)"
                       class="px-4 py-3 border-t border-[var(--border-default)]">
                    <div class="text-xs text-[var(--text-muted)] mb-2">
                      参考来源
                      <span v-if="msg.used_source_indices && msg.used_source_indices.length > 0">
                        · 引用了 {{ msg.used_source_indices.length }} 个
                      </span>
                    </div>
                    <div class="flex flex-wrap gap-1.5">
                      <button
                        v-for="(source, sidx) in (msg.filtered_sources && msg.filtered_sources.length > 0 ? msg.filtered_sources : msg.sources)"
                        :key="sidx"
                        @click="scrollToSource(source.index)"
                        class="source-card-btn text-xs px-2.5 py-1.5 rounded-lg bg-[var(--bg-tertiary)] border border-[var(--border-default)] text-[var(--text-secondary)] hover:bg-[var(--color-primary)] hover:text-white hover:border-[var(--color-primary)] transition-all flex items-center gap-1.5"
                      >
                        <span class="w-4 h-4 rounded-full bg-[var(--color-primary)] text-white text-[10px] flex items-center justify-center font-medium">{{
                          source.index }}</span>
                        <span v-if="source.source" class="max-w-[90px] truncate">{{ source.source }}</span>
                        <span v-if="source.page" class="text-[var(--text-muted)]">P{{ source.page }}</span>
                      </button>
                    </div>
                  </div>
                </template>
              </div>

              <!-- Source Cards (outside bubble) -->
              <div v-if="msg.expandedSources" class="mt-2.5 grid grid-cols-1 gap-2 pl-1">
                <div
                  v-for="(source, sidx) in msg.sources"
                  :key="sidx"
                  :id="`source-card-${source.index}`"
                  class="source-card p-3 bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-default)] text-sm"
                >
                  <div class="flex items-center gap-2 mb-1">
                    <span class="w-4 h-4 rounded-full bg-[var(--color-primary)] text-white text-[10px] flex items-center justify-center">{{ source.index }}</span>
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

    <!-- History Sidebar -->
    <ChatHistoryPanel
      :visible="showHistory"
      @close="showHistory = false"
      @loaded="onSessionLoaded"
      @deleted="onSessionDeleted"
    />
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'ChatView' })

import { computed, ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useChatStore } from '../stores/chat'
import type { ChatStreamMessage } from '../stores/chat'
import type { BotMood } from '../components/CopilotBotAvatar.vue'
import { useDocumentStore } from '../stores/document'
import ChatInput from '../components/chat/ChatInput.vue'
import ChatHistoryPanel from '../components/chat/ChatHistoryPanel.vue'
import DocumentPicker from '../components/common/DocumentPicker.vue'
import { buildChatMarkdown, downloadChatMarkdown } from '../composables/useChatExport'
import TTSPlayer from '../components/TTSPlayer.vue'
import { useMarkdown } from '../composables/useMarkdown'
import gsap from 'gsap'
import CopilotBotAvatar from '../components/CopilotBotAvatar.vue'
import { Plus, Download, Clock, User, RefreshRight, DocumentCopy, ArrowRight } from '@element-plus/icons-vue'

const chatStore = useChatStore()
const documentStore = useDocumentStore()
const readyDocs = computed(() => documentStore.readyDocuments)
const selectedDocs = ref<string[]>([])
const showHistory = ref(false)
const botMood = ref<BotMood>('idle')
const messagesRef = ref<HTMLElement | null>(null)
const route = useRoute()

const copiedMsgId = ref<string | number | null>(null)
let copiedResetTimer: ReturnType<typeof setTimeout> | null = null

async function copyMessage(msg: ChatStreamMessage): Promise<void> {
  try {
    await navigator.clipboard.writeText(msg.content)
    copiedMsgId.value = msg.id
    if (copiedResetTimer) clearTimeout(copiedResetTimer)
    copiedResetTimer = setTimeout(() => { copiedMsgId.value = null }, 2000)
  } catch (e) {
    console.error('Copy failed:', e)
  }
}

const { renderMarkdown: renderMarkdownBase } = useMarkdown()

const MD_CACHE_LIMIT = 200
const _mdCache = new Map<string, string>()

function _mdCacheGet(key: string): string | undefined {
  if (!_mdCache.has(key)) return undefined
  const val = _mdCache.get(key)
  _mdCache.delete(key)
  _mdCache.set(key, val!)
  return val
}

function _mdCacheSet(key: string, val: string): void {
  if (_mdCache.size >= MD_CACHE_LIMIT) {
    const oldest = _mdCache.keys().next().value
    if (oldest !== undefined) _mdCache.delete(oldest)
  }
  _mdCache.set(key, val)
}

function renderMarkdown(text: string, isStreaming = false): string {
  if (!text) return ''
  if (isStreaming) return text.replace(/</g, '&lt;').replace(/\n/g, '<br>')
  const cached = _mdCacheGet(text)
  if (cached) return cached
  let rendered = renderMarkdownBase(text)
  rendered = rendered.replace(/\[来源(\d+)\]/g, (_match, num: string) => {
    return `<sup class="source-badge" data-index="${num}">[${num}]</sup>`
  })
  _mdCacheSet(text, rendered)
  return rendered
}

function scrollToSource(index: number): void {
  const lastMsg = chatStore.messages[chatStore.messages.length - 1]
  if (lastMsg && lastMsg.role === 'assistant') {
    const msgIndex = chatStore.messages.length - 1
    chatStore.messages[msgIndex].expandedSources = !chatStore.messages[msgIndex].expandedSources
    setTimeout(() => {
      const card = document.getElementById(`source-card-${index}`)
      if (card) {
        card.scrollIntoView({ behavior: 'smooth', block: 'center' })
        card.classList.add('ring-2', 'ring-[var(--color-navy)]', 'bg-[var(--color-primary-light)]')
        setTimeout(() => card.classList.remove('ring-2', 'ring-[var(--color-navy)]', 'bg-[var(--color-primary-light)]'), 3000)
      }
    }, 100)
  }
}

async function handleSend(content: string): Promise<void> {
  if (selectedDocs.value.length === 0) return
  await chatStore.askQuestionStream(content, selectedDocs.value)
  await nextTick()
  scrollToBottom()
}

function handleStop(): void {
  chatStore.cancelStream()
}

function exportChat(): void {
  if (chatStore.messages.length === 0) return
  const md = buildChatMarkdown(chatStore.messages, chatStore.currentSessionTitle || '对话')
  downloadChatMarkdown(md)
}

function newChat(): void {
  chatStore.clearMessages()
  chatStore.currentSession = null
  chatStore.currentSessionTitle = ''
  showHistory.value = false
}

function onSessionLoaded(_sessionId: string): void {
  nextTick(() => scrollToBottom())
  showHistory.value = false
}

function onSessionDeleted(sessionId: string): void {
  if (chatStore.currentSession === sessionId) {
    newChat()
  }
}

function scrollToBottom(): void {
  if (messagesRef.value) {
    const el = messagesRef.value
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100
    if (nearBottom) {
      el.scrollTop = el.scrollHeight
    }
  }
}

let gsapCtx: gsap.Context | null = null

// Bot mood: stream starts → acknowledge → thinking → answering → done
function updateBotMood(msg: ChatStreamMessage, isLast: boolean): void {
  if (!isLast || msg.role !== 'assistant') { botMood.value = 'idle'; return }
  if (!msg.isStreaming) botMood.value = 'done'
  else if (msg.content) botMood.value = 'answering'
  else if (Array.isArray(msg.thinking) && msg.thinking.length > 0) botMood.value = 'thinking'
  else botMood.value = 'acknowledge'
}

watch(
  () => {
    const last = chatStore.messages[chatStore.messages.length - 1]
    return last ? { last } : null
  },
  (v) => {
    if (v) updateBotMood(v.last, true)
    else botMood.value = 'idle'
  },
  { deep: true }
)

let prevMsgCount = 0

watch(() => chatStore.messages.length, (newLen) => {
  nextTick(() => {
    scrollToBottom()
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
    const last = chatStore.messages[newLen - 1]
    if (last) updateBotMood(last, true)
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

  const contextQuery = route.query.context
  const docId = route.query.docId

  if (docId && !selectedDocs.value.includes(docId as string)) {
    selectedDocs.value = [docId as string]
  }

  if (contextQuery) {
    await handleSend(contextQuery as string)
  }

  gsapCtx = gsap.context(() => {
    const emptyIcon = messagesRef.value?.querySelector('.w-20.h-20')
    if (emptyIcon) {
      gsap.from(emptyIcon, { scale: 0.8, opacity: 0, duration: 0.5, ease: 'back.out(1.2)' })
    }
  }, messagesRef.value ?? undefined)
})

onUnmounted(() => {
  gsapCtx?.revert()
  if (copiedResetTimer) clearTimeout(copiedResetTimer)
})
</script>

<style>
/* 精修（批次3）：中文正文行高 1.7（舒适区），作用于 AI 回答正文 */
.prose {
  line-height: 1.7;
  font-size: 0.9rem;
}
.prose p {
  margin-bottom: 0.5em;
}
.prose p:last-child {
  margin-bottom: 0;
}
.prose ul, .prose ol {
  margin-top: 0.4em;
  margin-bottom: 0.6em;
  padding-left: 1.4em;
}
.prose li {
  margin-bottom: 0.25em;
}
.prose h1, .prose h2, .prose h3, .prose h4 {
  margin-top: 0.7em;
  margin-bottom: 0.3em;
  font-weight: 600;
  line-height: 1.4;
}
.prose h1:first-child, .prose h2:first-child, .prose h3:first-child, .prose h4:first-child {
  margin-top: 0;
}
.prose blockquote {
  margin: 0.6em 0;
  padding: 0.3em 0.8em;
}
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
  background: var(--gradient-brand);
  border-radius: 9999px;
  cursor: pointer;
  vertical-align: super;
  transition: all 0.2s ease;
}
.prose .source-badge:hover {
  transform: scale(1.1);
  box-shadow: 0 2px 8px color-mix(in srgb, var(--color-brand-from) 40%, transparent);
}

/* 思考过程折叠区 */
.thinking-section summary::-webkit-details-marker {
  display: none;
}
.thinking-section[open] .thinking-summary .el-icon {
  transform: rotate(90deg);
}
</style>
