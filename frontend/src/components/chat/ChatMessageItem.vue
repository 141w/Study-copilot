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
        ></div>
        <span v-if="message.isStreaming && message.content" class="stream-caret" aria-hidden="true"></span>

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
        </div>

        <!-- Sources chips -->
        <div
          v-if="message.sources && message.sources.length > 0 && (!message.isStreaming || message.content)"
          class="mt-4 pt-3 border-t border-[var(--border-default)]"
        >
          <div class="text-xs text-[var(--text-muted)] mb-2">
            参考来源
            <span v-if="message.used_source_indices && message.used_source_indices.length > 0">
              共 {{ message.used_source_indices.length }} 个
            </span>
          </div>
          <div class="space-y-0.5 source-stagger">
            <button
              v-for="(source, sidx) in (message.filtered_sources && message.filtered_sources.length > 0 ? message.filtered_sources : message.sources)"
              :key="sidx"
              @click="emit('scrollToSource', source.index)"
              class="source-card-btn source-row w-full text-left text-xs px-2 py-1.5 rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] transition-colors flex items-center gap-2"
            >
              <span
                class="w-4 h-4 rounded-full bg-[var(--color-primary)] text-[var(--text-inverse)] text-[10px] flex items-center justify-center font-medium flex-shrink-0"
              >
                {{ source.index }}
              </span>
              <span v-if="source.source" class="truncate flex-shrink min-w-0">{{ source.source }}</span>
              <span v-if="source.page" class="text-[var(--text-muted)] flex-shrink-0">P{{ source.page }}</span>
            </button>
          </div>
        </div>

        <!-- Expanded Source Cards -->
        <ChatSourceCards v-if="message.expandedSources" :sources="message.sources" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ArrowRight, DocumentCopy } from '@/components/icons'
import type { ChatStreamMessage } from '@/stores/chat'
import type { BotMood } from '@/components/CopilotBotAvatar.vue'
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
}>()

// 默认折叠：两个思考过程均初始保持折叠
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
</style>
