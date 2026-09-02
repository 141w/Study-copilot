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
          <!-- 按钮尺寸统一：手写 36px 按钮换 el-button（32px，与全站一致） -->
          <!-- New Chat Button -->
          <el-button type="primary" :icon="Plus" @click="newChat">新建对话</el-button>

          <!-- Export Chat Button -->
          <el-button
            :icon="Download"
            :disabled="chatStore.messages.length === 0"
            @click="exportChat"
          >
            导出对话
          </el-button>

          <!-- Toggle History Sidebar -->
          <el-button
            :type="showHistory ? 'primary' : 'default'"
            :icon="Clock"
            @click="showHistory = !showHistory"
          >
            {{ showHistory ? '隐藏记录' : '历史记录' }}
          </el-button>

          <router-link
            to="/model-config"
            class="text-sm text-[var(--text-muted)] hover:text-[var(--color-primary)]"
          >
            模型配置
          </router-link>
        </div>
      </div>

      <!-- Document Selector（P2-3：DocumentPicker multiple 标签模式） -->
      <div class="border-b border-[var(--border-default)] px-6 py-3 bg-[var(--bg-secondary)]">
        <DocumentPicker
          v-model="selectedDocs"
          mode="multiple"
          label="参考文档"
          :documents="readyDocs"
        />
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
        
        <div v-else class="max-w-3xl mx-auto space-y-6">
          <div
            v-for="(msg, idx) in chatStore.messages"
            :key="idx"
            class="flex gap-4"
            :class="msg.role === 'user' ? 'flex-row-reverse' : ''"
          >
            <!-- Avatar with mood-driven animation -->
            <div class="flex-shrink-0">
              <CopilotBotAvatar
                v-if="msg.role === 'assistant'"
                :is-streaming="msg.isStreaming"
                :size="32"
                :mood="msg === chatStore.messages[chatStore.messages.length - 1] ? botMood : 'idle'"
              />
              <div
                v-else
                class="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center bg-[var(--color-primary)] text-white"
              >
                <el-icon class="w-4 h-4"><User /></el-icon>
              </div>
            </div>

            <!-- Message Content -->
            <div
              class="flex-1 px-4 py-3 rounded-2xl max-w-[80%]"
              :class="msg.role === 'user' ? 'bg-[var(--color-primary)] text-white' : 'bg-[var(--surface-card)] shadow-sm border border-[var(--border-default)] text-[var(--text-primary)]'"
            >
              <!-- 思考中状态 -->
              <div v-if="msg.role === 'assistant' && msg.isStreaming && !msg.content" class="flex items-center gap-2 text-[var(--text-muted)]">
              <el-icon class="w-4 h-4 is-loading"><RefreshRight /></el-icon>
                <span>思考中...</span>
              </div>
              <div v-else class="prose prose-sm max-w-none" v-html="renderMarkdown(msg.content, msg.isStreaming)"></div>

              <!-- 消息操作栏：朗读 + 复制（仅助手消息、非流式中、有内容时显示）
                   按钮尺寸统一：复制钮由 26px 手写改 el-button small（24px），
                   与 TTSPlayer 朗读钮同高 -->
              <div
                v-if="msg.role === 'assistant' && !msg.isStreaming && msg.content"
                class="flex items-center gap-3 mt-2 pt-2 border-t border-[var(--border-default)]"
              >
                <TTSPlayer :text="msg.content" />
                <el-button
                  size="small"
                  text
                  bg
                  @click="copyMessage(msg)"
                  title="复制回答"
                >
                  <el-icon class="w-3.5 h-3.5 mr-1"><DocumentCopy /></el-icon>
                  {{ copiedMsgId === msg.id ? '已复制' : '复制' }}
                </el-button>
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
                    class="source-card-btn text-xs px-3 py-2 rounded-xl bg-[var(--bg-tertiary)] border border-[var(--border-default)] text-[var(--text-secondary)] hover:bg-[var(--color-primary)] hover:text-white hover:border-[var(--color-primary)] transition-all flex items-center gap-1.5"
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
                  class="source-card p-3 bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-default)] text-sm"
                >
                  <div class="flex items-center gap-2 mb-1">
                    <span class="w-5 h-5 rounded-full bg-[var(--color-primary)] text-white text-xs flex items-center justify-center">
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

<script setup lang="ts">
// defineOptions 是编译器宏，无需导入
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
import { Plus, Download, Clock, User, RefreshRight, DocumentCopy } from '@element-plus/icons-vue'

const chatStore = useChatStore()
const documentStore = useDocumentStore()
const readyDocs = computed(() => documentStore.readyDocuments)
const selectedDocs = ref<string[]>([])
const showHistory = ref(false)
const botMood = ref<BotMood>('idle')
const messagesRef = ref<HTMLElement | null>(null)
const route = useRoute()

// 复制消息状态
const copiedMsgId = ref<string | number | null>(null)
// P1-2：复制状态复位 timer，卸载时清理（原悬空未回收）
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

// Memoize markdown renders: key = content text, value = rendered HTML.
// Streaming messages (isStreaming=true) bypass cache and render as plain text.
// P1-1：LRU 上限 —— 原无界 Map 在长会话中随消息数线性增长（内存泄漏隐患）
const MD_CACHE_LIMIT = 200
const _mdCache = new Map<string, string>()

function _mdCacheGet(key: string): string | undefined {
  if (!_mdCache.has(key)) return undefined
  // touch：删除重插实现 LRU 顺序
  const val = _mdCache.get(key)
  _mdCache.delete(key)
  _mdCache.set(key, val!)
  return val
}

function _mdCacheSet(key: string, val: string): void {
  if (_mdCache.size >= MD_CACHE_LIMIT) {
    // 逐出最旧（首个插入且未再访问的 key）
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
    // 切换来源卡片展开状态
    const msgIndex = chatStore.messages.length - 1
    chatStore.messages[msgIndex].expandedSources = !chatStore.messages[msgIndex].expandedSources

    setTimeout(() => {
      // 滚动到对应的来源卡片
      const card = document.getElementById(`source-card-${index}`)
      if (card) {
        card.scrollIntoView({ behavior: 'smooth', block: 'center' })
        card.classList.add('ring-2', 'ring-[var(--color-navy)]', 'bg-[var(--color-primary-light)]')
        setTimeout(() => card.classList.remove('ring-2', 'ring-[var(--color-navy)]', 'bg-[var(--color-primary-light)]'), 3000)
      }
    }, 100)
  }
}

// 注：原 scrollToReference（来源卡跳回正文徽章）从未接线——模板的来源卡
// 点击走的是 scrollToSource，该死函数已在工程化批次删除。

async function handleSend(content: string): Promise<void> {
  if (selectedDocs.value.length === 0) return
  // 使用流式接口
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
  // 面板已完成 fetchHistory 与标题恢复；父级负责滚动与收起
  nextTick(() => scrollToBottom())
  showHistory.value = false
}

function onSessionDeleted(sessionId: string): void {
  // 删除的是当前会话时重置视图
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

// GSAP animation context for cleanup
let gsapCtx: gsap.Context | null = null

// ── Bot mood driven by message state ──────────────────────────────────
function updateBotMood(msg: ChatStreamMessage, isLast: boolean): void {
  if (!isLast || msg.role !== 'assistant') { botMood.value = 'idle'; return }
  if (msg.isStreaming && !msg.content) botMood.value = 'acknowledge'
  else if (msg.isStreaming && msg.content) botMood.value = 'answering'
  else botMood.value = 'done'
}

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
    // Update bot mood for the last assistant message
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

  // 处理来自其他页面的上下文参数
  const contextQuery = route.query.context
  const docId = route.query.docId

  if (docId && !selectedDocs.value.includes(docId as string)) {
    selectedDocs.value = [docId as string]
  }

  if (contextQuery) {
    await handleSend(contextQuery as string)
  }

  // Animate the empty state icon
  gsapCtx = gsap.context(() => {
    const emptyIcon = messagesRef.value?.querySelector('.w-20.h-20')
    if (emptyIcon) {
      gsap.from(emptyIcon, { scale: 0.8, opacity: 0, duration: 0.5, ease: 'back.out(1.2)' })
    }
  }, messagesRef.value ?? undefined)
})

onUnmounted(() => {
  gsapCtx?.revert()
  // P1-2：清理悬空 timer
  if (copiedResetTimer) clearTimeout(copiedResetTimer)
})
</script>

<style>
/* 精修（批次3）：中文正文行高 1.7（舒适区），作用于 AI 回答正文 */
.prose p {
  line-height: var(--leading-body, 1.7);
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
</style>