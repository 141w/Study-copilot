<template>
  <div class="group">
    <!-- User message -->
    <div v-if="message.role === 'user'" class="flex justify-end msg-enter">
      <div class="max-w-[85%] min-w-0">
        <div
          class="text-[0.9rem] leading-[1.75] text-[var(--text-primary)] px-4 py-2.5 rounded-lg rounded-tr-sm bg-[var(--bg-hover)] border border-[var(--border-default)] inline-block max-w-full break-words whitespace-pre-wrap"
        >
          {{ formatUserContent(message.content) }}
        </div>
      </div>
    </div>

    <!-- Assistant message -->
    <div v-else-if="message.role === 'assistant'" class="msg-enter flex items-start gap-3 sm:gap-4 relative">
      <!-- Left Column: Bot Avatar (Sticky so it stays visible without occlusion when scrolling) -->
      <div class="flex-shrink-0 w-11 sticky top-4 z-10 self-start flex justify-center">
        <CopilotBotAvatar
          v-if="showAvatar"
          class="bot-avatar-flip"
          :is-streaming="message.isStreaming"
          :size="44"
          :mood="isLatestAssistant ? (avatarMood || 'idle') : 'idle'"
          :expression="isLatestAssistant ? (avatarExpr || 'neutre') : 'neutre'"
        />
        <div v-else class="w-11"></div>
      </div>

      <!-- Right Column: Header ('S' aligned with body) + Answer Body -->
      <div class="flex-1 min-w-0 pl-0">
        <!-- Author line: 'S' starts at 0px of this column, perfectly aligned with the message body below -->
        <div class="flex items-center gap-2 mb-1.5 h-6">
          <span class="text-sm font-semibold text-[var(--text-primary)] leading-none">Study Copilot</span>
        </div>

        <!-- 1. Initial Waiting state (before any thinking steps, reasoning, or content arrive) -->
        <div
          v-if="message.isStreaming && !message.content && !message.reasoning && (!message.thinking || (Array.isArray(message.thinking) && message.thinking.length === 0))"
          class="flex items-center gap-1.5 py-2"
          aria-label="思考中"
        >
          <span class="thinking-dot"></span>
          <span class="thinking-dot" style="animation-delay: 0.15s"></span>
          <span class="thinking-dot" style="animation-delay: 0.3s"></span>
        </div>

        <!-- 2. Deck 1: Agentic 决策与反思流水线 (Macro Thinking Timeline) -->
        <details
          v-if="Array.isArray(message.thinking) && message.thinking.length > 0"
          :open="isThinkingOpen"
          class="thinking-section mb-2.5 rounded-xl border border-[var(--border-default)] bg-[var(--bg-secondary)]/40 overflow-hidden transition-all"
        >
          <summary
            class="thinking-summary px-3 py-2 text-xs font-medium text-[var(--text-muted)] cursor-pointer select-none hover:bg-[var(--bg-hover)] transition-colors list-none"
            @click.prevent="isThinkingOpen = !isThinkingOpen"
          >
            <!-- 第一行：主标题与规划状态 -->
            <div class="flex items-center gap-2 min-w-0">
              <el-icon class="w-3.5 h-3.5 transition-transform duration-200 shrink-0 text-[var(--text-muted)]" :class="{ 'rotate-90': isThinkingOpen }">
                <ArrowRight />
              </el-icon>
              <span class="font-medium text-[var(--text-primary)] shrink-0">
                Agentic 思考过程 ({{ message.thinking.length }} 步)
              </span>
              <span
                v-if="isAgenticThinking"
                class="inline-flex items-center gap-1 text-[10px] text-[var(--color-primary)] font-normal shrink-0"
              >
                <span class="thinking-dot !w-1.5 !h-1.5"></span>
                <span>规划质检中</span>
              </span>
            </div>

            <!-- 第二行：思考过程中展示当前动态（双行），思考结束后自动隐藏（单行） -->
            <div
              v-if="!isThinkingOpen && isAgenticThinking && latestThinkingStep"
              class="flex items-center gap-1.5 mt-1.5 pl-5 text-[11px] text-[var(--text-muted)] min-w-0"
            >
              <span
                :class="['px-1.5 py-0.2 text-[9px] font-medium rounded border shrink-0', latestThinkingStep.badge.color]"
              >
                {{ latestThinkingStep.badge.label }}
              </span>
              <span class="truncate flex-1 text-[var(--text-secondary)]">
                {{ latestThinkingStep.detail }}
              </span>
            </div>
          </summary>
          <div class="px-3 pb-2.5 pt-1 border-t border-[var(--border-subtle)] space-y-2 text-xs">
            <div
              v-for="(t, ti) in message.thinking"
              :key="ti"
              class="flex items-start gap-2 pt-1 text-[var(--text-secondary)] leading-relaxed"
            >
              <span
                :class="['px-1.5 py-0.5 text-[10px] font-medium rounded border flex-shrink-0 tracking-wide', getStepBadge(typeof t === 'object' && t ? t.step : t).color]"
              >
                {{ getStepBadge(typeof t === 'object' && t ? t.step : t).label }}
              </span>
              <span class="flex-1 min-w-0 text-[var(--text-secondary)] break-words">{{ typeof t === 'object' && t ? t.detail : t }}</span>
            </div>
          </div>
        </details>

        <!-- 3. Deck 2: 底层模型原生 CoT 深度思考流 (Native CoT Reasoning Stream) -->
        <details
          v-if="message.reasoning"
          :open="isReasoningOpen"
          class="reasoning-box mb-2.5 rounded-xl border border-[var(--border-default)] bg-[var(--bg-secondary)]/30 overflow-hidden transition-all"
        >
          <summary
            class="reasoning-summary px-3 py-2 text-xs font-medium text-[var(--text-muted)] cursor-pointer select-none hover:bg-[var(--bg-hover)] transition-colors list-none"
            @click.prevent="isReasoningOpen = !isReasoningOpen"
          >
            <!-- 第一行：标题与状态 -->
            <div class="flex items-center gap-2 min-w-0">
              <el-icon class="w-3.5 h-3.5 transition-transform duration-200 shrink-0 text-[var(--text-muted)]" :class="{ 'rotate-90': isReasoningOpen }">
                <ArrowRight />
              </el-icon>
              <span
                v-if="isCoTThinking"
                class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shrink-0"
              ></span>
              <span v-else class="w-2 h-2 rounded-full bg-emerald-500/70 shrink-0"></span>
              <span class="font-medium text-[var(--text-primary)] shrink-0">
                {{ isCoTThinking ? '正在深度思考...' : '已完成深度思考' }}
              </span>
            </div>

            <!-- 第二行：思考过程中展示当前思考流最新片段（双行），思考结束后自动隐藏（单行） -->
            <div
              v-if="!isReasoningOpen && isCoTThinking"
              class="flex items-center gap-1.5 mt-1.5 pl-5 text-[11px] text-[var(--text-muted)] min-w-0"
            >
              <span class="truncate flex-1 font-mono text-[10.5px]">
                {{ currentReasoningSnippet }}
              </span>
              <span class="stream-caret shrink-0" aria-hidden="true"></span>
            </div>
          </summary>
          <div class="px-3.5 py-2.5 border-t border-[var(--border-subtle)] text-xs text-[var(--text-secondary)] leading-relaxed pl-3 border-l-2 border-l-emerald-500/50 bg-[var(--bg-tertiary)]/20">
            <div class="prose prose-xs max-w-none text-[var(--text-secondary)] whitespace-pre-wrap font-sans opacity-90" v-html="renderedReasoningText"></div>
            <span v-if="message.isStreaming && !message.content" class="stream-caret" aria-hidden="true"></span>
          </div>
        </details>

        <!-- 4. Deck 3: 正式回答 (Final Answer Body) -->
        <div
          v-if="message.isStreaming || message.content"
          class="text-[0.9rem] leading-[1.75] text-[var(--text-primary)] prose prose-sm max-w-none"
          v-html="renderedMarkdown"
          @click="handleContentClick"
        ></div>
        <span v-if="message.isStreaming && message.content" class="stream-caret" aria-hidden="true"></span>

        <!-- 5. 学习笔记已保存卡片 -->
        <div
          v-if="savedNoteInfo"
          class="saved-note-card my-3 p-3 rounded-xl border border-emerald-500/30 bg-emerald-500/5 dark:bg-emerald-950/20 flex items-center justify-between gap-3 text-xs"
        >
          <div class="flex items-center gap-2.5 min-w-0">
            <div class="w-7 h-7 rounded-lg bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0">
              <el-icon class="w-4 h-4"><EditPen /></el-icon>
            </div>
            <div class="min-w-0">
              <div class="flex items-center gap-1.5 flex-wrap">
                <span class="font-medium text-[var(--text-primary)] truncate max-w-[200px] sm:max-w-xs">
                  {{ savedNoteInfo.title }}
                </span>
                <span class="px-1.5 py-0.2 text-[10px] rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 shrink-0">
                  已存入笔记
                </span>
              </div>
              <div v-if="savedNoteInfo.tags && savedNoteInfo.tags.length > 0" class="flex items-center gap-1.5 mt-1 text-[11px] text-[var(--text-muted)] flex-wrap">
                <span v-for="tag in savedNoteInfo.tags" :key="tag" class="text-emerald-600/80 dark:text-emerald-400/80">
                  #{{ tag }}
                </span>
              </div>
            </div>
          </div>
          <el-button
            size="small"
            type="primary"
            plain
            class="shrink-0 !text-xs !px-2.5"
            @click="navigateToNote(savedNoteInfo.id)"
          >
            查看笔记
          </el-button>
        </div>

        <!-- Actions -->
        <div
          v-if="!message.isStreaming && message.content"
          class="flex items-center gap-2 mt-2 opacity-100 md:opacity-0 md:group-hover:opacity-100 transition-opacity"
        >
          <TTSPlayer :text="message.content" />
          <el-button size="small" text bg @click="emit('copy', message)" title="复制回答">
            <el-icon class="w-3.5 h-3.5 mr-1"><DocumentCopy /></el-icon>
            {{ isCopied ? '已复制' : '复制' }}
          </el-button>
          <el-button
            v-if="!savedNoteInfo"
            size="small"
            text
            bg
            :loading="isSavingNote"
            @click="handleSaveNote"
            title="将回答提炼并存入个人笔记"
          >
            <el-icon class="w-3.5 h-3.5 mr-1"><EditPen /></el-icon>
            存为笔记
          </el-button>
          <span
            v-else
            class="inline-flex items-center gap-1 text-[11px] text-emerald-600 dark:text-emerald-400 select-none px-2 py-0.5 rounded bg-emerald-500/10"
          >
            <el-icon class="w-3 h-3"><EditPen /></el-icon>
            已存笔记
          </span>
        </div>

        <!-- 来源：流式研究阶段仅摘要；正文开始/结束后展示可折叠完整卡 -->
        <div
          v-if="displaySources.length > 0"
          class="sources-section"
          data-test="sources-section"
        >
          <!-- 研究阶段：不打断阅读，只给一行定位摘要 -->
          <div
            v-if="isResearchPhase"
            class="sources-hint"
            data-test="sources-research-hint"
          >
            <span class="relative flex h-2 w-2 shrink-0">
              <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span class="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span class="sources-hint__text">研究中，已定位 {{ displaySources.length }} 个来源…</span>
          </div>

          <!-- 正文出现或流结束后：可折叠完整来源卡 -->
          <template v-else>
            <button
              type="button"
              class="sources-toggle"
              data-test="sources-toggle"
              :aria-expanded="isSourcesOpen"
              @click="isSourcesOpen = !isSourcesOpen"
            >
              <div class="sources-toggle__left">
                <div class="sources-toggle__icon">
                  <el-icon class="w-3.5 h-3.5"><Reading /></el-icon>
                </div>
                <span class="sources-toggle__title">
                  参考来源
                </span>
                <span class="sources-toggle__count">
                  <span v-if="usedSourceCount > 0">共 {{ usedSourceCount }} 个</span>
                  <span v-else>共 {{ displaySources.length }} 个</span>
                </span>
              </div>

              <div class="sources-toggle__right">
                <el-icon
                  class="sources-toggle__arrow w-3.5 h-3.5"
                  :class="{ 'sources-toggle__arrow--open': isSourcesOpen }"
                >
                  <ArrowRight />
                </el-icon>
              </div>
            </button>
            <div v-if="isSourcesOpen" data-test="sources-body">
              <ChatSourceCards
                ref="sourceCardsRef"
                :sources="displaySources"
                @open-source="openSourceDocument"
              />
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowRight, DocumentCopy, EditPen, Reading } from '@/components/icons'
import type { ChatStreamMessage } from '@/stores/chat'
import { useChatStore } from '@/stores/chat'
import { useDocumentStore } from '@/stores/document'
import type { BotMood } from '@/components/CopilotBotAvatar.vue'
import type { Source } from '@/types/models'
import type { ExpressionId } from '@/bot/expressions'
import CopilotBotAvatar from '@/components/CopilotBotAvatar.vue'
import TTSPlayer from '@/components/TTSPlayer.vue'
import ChatSourceCards from './ChatSourceCards.vue'
import { useMarkdown } from '@/composables/useMarkdown'

const props = defineProps<{
  message: ChatStreamMessage
  renderedMarkdown?: string
  renderedReasoning?: string
  showAvatar?: boolean
  isLatestAssistant?: boolean
  avatarMood?: BotMood
  avatarExpr?: ExpressionId
  isCopied?: boolean
}>()

const emit = defineEmits<{
  (e: 'copy', msg: ChatStreamMessage): void
  (e: 'scrollToSource', index: number): void
  (e: 'saveNote', msg: ChatStreamMessage): void
}>()

const router = useRouter()
const chatStore = useChatStore()
const documentStore = useDocumentStore()
const isSavingNote = ref(false)

// 若文档库未加载（历史会话恢复），拉取一次以便 UUID source → 文件名
if ((documentStore.documents || []).length === 0) {
  documentStore.fetchDocuments().catch(() => {})
}

/** chunk.source 可能是 document_id（UUID）——用文档库映射回文件名 */
function sourceLabel(s: Source): string {
  if (!s) return ''
  const raw = s.source || ''
  if (!raw) return s.document_id || ''
  if (/^[0-9a-f]{8}-[0-9a-f]{4}-/i.test(raw)) {
    const doc = (documentStore.documents || []).find((d) => d.id === raw || d.id === s.document_id)
    if (doc?.filename) return doc.filename
  }
  return raw
}

/** 优先展示被引用来源；无 filter 时展示全部。展示名映射为可读文件名 */
const displaySources = computed<Source[]>(() => {
  const filtered = props.message.filtered_sources
  const all = props.message.sources
  const list = Array.isArray(filtered) && filtered.length > 0 ? filtered : (Array.isArray(all) ? all : [])
  return list.map((s) => ({ ...s, source: sourceLabel(s) }))
})

const usedSourceCount = computed(() => {
  const n = props.message.used_source_indices?.length
  return typeof n === 'number' && n > 0 ? n : 0
})

/**
 * 深度研究工具阶段：流式中且正文未到——只显示摘要行，避免来源卡抢占阅读区。
 * 首 token 到达或流结束后进入完整可折叠展示。
 */
const isResearchPhase = computed(() => {
  return Boolean(props.message.isStreaming && !props.message.content)
})

/** 完整来源卡展开态：历史消息默认展开；流式结束后自动展开一次 */
const isSourcesOpen = ref(false)

function syncSourcesOpenAfterStream(): void {
  if (displaySources.value.length > 0) {
    isSourcesOpen.value = true
  }
}

// 正文开始吐字：离开研究阶段，铺开完整卡
watch(
  () => Boolean(props.message.content),
  (hasContent, hadContent) => {
    if (hasContent && !hadContent) {
      isSourcesOpen.value = false
      // 首 token 后给用户完整来源入口；默认展开一次便于核对引用
      if (displaySources.value.length > 0) {
        isSourcesOpen.value = true
      }
    }
  }
)

// 流结束：确保完整区可见且默认展开
watch(
  () => props.message.isStreaming,
  (isStreaming, wasStreaming) => {
    if (!isStreaming && wasStreaming) {
      syncSourcesOpenAfterStream()
    }
  }
)

// 历史会话挂载 / 消息切换：非流式且有来源时默认展开
watch(
  () => props.message.id,
  () => {
    isSourcesOpen.value = Boolean(
      !props.message.isStreaming && displaySources.value.length > 0
    )
  },
  { immediate: true }
)

// 点击正文内的 [来源N] 跳转时，确保来源区是打开的
watch(
  () => props.message.expandedSources,
  (open) => {
    if (open) isSourcesOpen.value = true
  }
)

const sourceCardsRef = ref<InstanceType<typeof ChatSourceCards> | null>(null)

/** 打开文档阅读器并定位到来源页/关键词（T17） */
function openSourceDocument(source: Source): void {
  const docId = source.document_id || ''
  const page = source.page ? String(source.page) : undefined
  const q = (source.text || '').slice(0, 40).trim() || undefined
  const query: Record<string, string> = {}
  if (docId) query.document_id = docId
  if (page) query.page = page
  if (q) query.q = q
  // 来源文件名也可作为兜底定位键
  if (!docId && source.source) query.filename = source.source
  router.push({ name: 'documents', query })
}

function handleContentClick(e: MouseEvent): void {
  const target = (e.target as HTMLElement).closest('.source-badge')
  if (target) {
    const idx = target.getAttribute('data-index')
    if (idx) {
      const num = parseInt(idx, 10)
      if (!isNaN(num)) {
        isSourcesOpen.value = true
        emit('scrollToSource', num)
        nextTick(() => {
          sourceCardsRef.value?.expand(num)
        })
      }
    }
  }
}

const savedNoteInfo = computed(() => {
  return props.message.savedNote || props.message.saved_note || null
})

async function handleSaveNote() {
  if (isSavingNote.value || !props.message.id || savedNoteInfo.value) return
  isSavingNote.value = true
  emit('saveNote', props.message)
  try {
    const note = await chatStore.saveMessageAsNote(props.message.id)
    ElMessage.success(`已保存至笔记：《${note.title}》`)
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || err?.message || '保存笔记失败')
  } finally {
    isSavingNote.value = false
  }
}

function navigateToNote(noteId?: string) {
  if (router) {
    router.push({ path: '/notes', query: noteId ? { id: noteId } : undefined })
  } else if (typeof window !== 'undefined') {
    window.location.href = noteId ? `/notes?id=${noteId}` : '/notes'
  }
}

// 与快速模式一致：思考面板默认折叠；流式中只靠摘要行展示最新步骤，结束后自动收起
const isThinkingOpen = ref(false)
const isReasoningOpen = ref(false)

// 监听思考完成：当正式回答正文开始吐字，或流式推送结束时，自动收起为单行
watch(
  () => Boolean(props.message.content),
  (hasContent, hadContent) => {
    if (hasContent && !hadContent) {
      isThinkingOpen.value = false
      isReasoningOpen.value = false
    }
  }
)

watch(
  () => props.message.isStreaming,
  (isStreaming, wasStreaming) => {
    if (!isStreaming && wasStreaming) {
      isThinkingOpen.value = false
      isReasoningOpen.value = false
    }
  }
)

watch(
  () => props.message.id,
  () => {
    isThinkingOpen.value = false
    isReasoningOpen.value = false
  }
)

const { renderMarkdown: renderMd } = useMarkdown()

const renderedReasoningText = computed(() => {
  if (props.renderedReasoning) return props.renderedReasoning
  if (!props.message.reasoning) return ''
  return renderMd(props.message.reasoning)
})

// 是否处于思考中状态（思考中呈现双行，结束后呈现单行）
const isAgenticThinking = computed(() => {
  return Boolean(props.message.isStreaming && !props.message.content && !props.message.reasoning)
})

const isCoTThinking = computed(() => {
  return Boolean(props.message.isStreaming && !props.message.content && props.message.reasoning)
})

// 思考中第二行：展示当前正在执行的 Agentic 决策步骤
const latestThinkingStep = computed(() => {
  if (!props.message.thinking) return null
  if (typeof props.message.thinking === 'string') {
    return {
      badge: { label: '决策步骤', color: 'bg-slate-500/10 text-slate-600 dark:text-slate-400 border-slate-500/20' },
      detail: props.message.thinking.replace(/[#*`_~>\n\r]/g, ' ').replace(/\s+/g, ' ').trim()
    }
  }
  if (!Array.isArray(props.message.thinking) || props.message.thinking.length === 0) return null
  const steps = props.message.thinking
  const last = steps[steps.length - 1]
  if (!last) return null
  if (typeof last === 'string') {
    return {
      badge: { label: '决策步骤', color: 'bg-slate-500/10 text-slate-600 dark:text-slate-400 border-slate-500/20' },
      detail: (last as string).replace(/[#*`_~>\n\r]/g, ' ').replace(/\s+/g, ' ').trim()
    }
  }
  return {
    badge: getStepBadge(last.step),
    detail: (last.detail || '').replace(/[#*`_~>\n\r]/g, ' ').replace(/\s+/g, ' ').trim()
  }
})

// 思考中第二行：展示当前深度思考最新推导文本片段
const currentReasoningSnippet = computed(() => {
  if (!props.message.reasoning) return ''
  const lines = props.message.reasoning
    .replace(/[#*`_~>\r]/g, ' ')
    .split('\n')
    .map(l => l.trim())
    .filter(Boolean)
  if (lines.length === 0) return '正在梳理推导思路…'
  return lines[lines.length - 1] || '正在梳理推导思路…'
})

function getStepBadge(step: string | number): { label: string; color: string } {
  switch (String(step)) {
    case 'intent_analysis':
      return { label: '意图拆解', color: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20' }
    case 'strategy_select':
      return { label: '策略规划', color: 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20' }
    case 'adaptive_retrieve':
      return { label: '知识检索', color: 'bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border-cyan-500/20' }
    case 'query_decompose':
      return { label: '多跳拆解', color: 'bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border-indigo-500/20' }
    case 'retrieval_check':
      return { label: '相关度质检', color: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20' }
    case 'retrieval_retry':
      return { label: '重写纠错', color: 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20' }
    case 'reflection_pass':
      return { label: '事实核验通过', color: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20' }
    case 'reflection_fail':
      return { label: '反思修正', color: 'bg-orange-500/10 text-orange-600 dark:text-orange-400 border-orange-500/20' }
    // Deep research Agent steps
    case 'agent_start':
      return { label: '研究启动', color: 'bg-violet-500/10 text-violet-600 dark:text-violet-400 border-violet-500/20' }
    case 'agent_think':
      return { label: '自主研判', color: 'bg-violet-500/10 text-violet-600 dark:text-violet-400 border-violet-500/20' }
    case 'agent_act':
      return { label: '执行行动', color: 'bg-fuchsia-500/10 text-fuchsia-600 dark:text-fuchsia-400 border-fuchsia-500/20' }
    case 'tool_call':
      return { label: '调用工具', color: 'bg-sky-500/10 text-sky-600 dark:text-sky-400 border-sky-500/20' }
    case 'tool_result':
      return { label: '工具结果', color: 'bg-teal-500/10 text-teal-600 dark:text-teal-400 border-teal-500/20' }
    case 'agent_synthesize':
      return { label: '证据汇总', color: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20' }
    case 'agent_error':
      return { label: '研究异常', color: 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20' }
    case 'agent_truncated':
      return { label: '输出截断', color: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20' }
    case 'agent_stall':
      return { label: '循环熔断', color: 'bg-orange-500/10 text-orange-600 dark:text-orange-400 border-orange-500/20' }
    default:
      return { label: '决策步骤', color: 'bg-slate-500/10 text-slate-600 dark:text-slate-400 border-slate-500/20' }
  }
}

function formatUserContent(content: string): string {
  if (!content) return ''
  return content.replace(/\\r\\n/g, '\n').replace(/\\n/g, '\n')
}
</script>

<style scoped>
summary::-webkit-details-marker {
  display: none;
}
summary {
  list-style: none;
}

/* ==================== 来源区（sources-section）：scoped 纯 CSS ====================
   项目未启用 Tailwind preflight（global.css 只有 @tailwind utilities）：
   border 工具类因 border-style 缺省 none 整条不可见；var()/NN 修饰符静默失效
   （回退 currentColor 画出黑线）；裸 button 带 UA 原生皮肤（ButtonFace + outset）。
   来源区样式全部在此显式声明，不依赖工具类；令牌取自 variables.css。 */
.sources-section {
  margin-top: 1rem;
  padding-top: 0.875rem;
  border-top: 1px solid color-mix(in srgb, var(--border-default) 80%, transparent);
}
.dark .sources-section {
  border-top-color: rgba(255, 255, 255, 0.1);
}

/* 研究阶段提示条 */
.sources-hint {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-xl);
  background: color-mix(in srgb, var(--bg-secondary) 30%, transparent);
  color: var(--text-secondary);
  font-size: 0.75rem;
}
.dark .sources-hint {
  border-color: rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.02);
  color: #a1a1aa;
}
.sources-hint__text {
  font-weight: 500;
}

/* 「参考来源」折叠按钮：剥 UA 皮肤；无边框无底色，与来源卡同语言，hover 微底色 */
.sources-toggle {
  -webkit-appearance: none;
  appearance: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  width: 100%;
  margin-bottom: 0.625rem;
  padding: 0.625rem 0.875rem;
  border: 0;
  border-radius: var(--radius-xl);
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  user-select: none;
  cursor: pointer;
  transition: background-color 0.2s ease;
}
.sources-toggle:hover {
  background: color-mix(in srgb, var(--bg-primary) 97%, var(--text-primary));
}
.sources-toggle:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: -2px;
}
.dark .sources-toggle:focus-visible {
  outline-color: rgba(255, 255, 255, 0.7);
}
.sources-toggle__left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
  flex-wrap: wrap;
}
.sources-toggle__icon {
  width: 1.25rem;
  height: 1.25rem;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  background: var(--bg-tertiary);
  color: var(--text-muted);
  transition: color 0.2s ease;
}
.dark .sources-toggle__icon {
  background: rgba(255, 255, 255, 0.1);
  color: #a1a1aa;
}
.sources-toggle:hover .sources-toggle__icon {
  color: var(--text-primary);
}
.dark .sources-toggle:hover .sources-toggle__icon {
  color: #ffffff;
}
.sources-toggle__title {
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--text-primary);
}
.dark .sources-toggle__title {
  color: #e4e4e7;
}
.sources-toggle__count {
  padding: 0.125rem 0.375rem;
  border: 1px solid rgba(228, 228, 231, 0.8);
  border-radius: var(--radius-md);
  background: #f4f4f5;
  color: #52525b;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px;
}
.dark .sources-toggle__count {
  border-color: rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.1);
  color: #d4d4d8;
}
.sources-toggle__right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}
.sources-toggle__arrow {
  color: var(--text-muted);
  transition: transform 0.2s ease, color 0.2s ease;
}
.dark .sources-toggle__arrow {
  color: #a1a1aa;
}
.sources-toggle:hover .sources-toggle__arrow {
  color: var(--text-primary);
}
.dark .sources-toggle:hover .sources-toggle__arrow {
  color: #ffffff;
}
.sources-toggle__arrow--open {
  transform: rotate(90deg);
}
</style>
