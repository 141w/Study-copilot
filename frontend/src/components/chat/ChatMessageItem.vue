<template>
  <div class="group">
    <!-- User message -->
    <div v-if="message.role === 'user'" class="flex justify-end msg-enter">
      <div class="max-w-[85%] min-w-0">
        <div
          class="text-[0.9rem] leading-[1.75] text-[var(--text-primary)] px-4 py-2.5 rounded-lg rounded-tr-sm bg-[var(--bg-hover)] border border-[var(--border-default)] inline-block max-w-full break-words whitespace-pre-wrap"
        >
          {{ message.content }}
        </div>
      </div>
    </div>

    <!-- Assistant message -->
    <div v-else-if="message.role === 'assistant'" class="msg-enter">
      <!-- Author line -->
      <div class="flex items-center gap-2.5 mb-1.5">
        <CopilotBotAvatar
          v-if="showAvatar"
          class="bot-avatar-flip"
          :is-streaming="message.isStreaming"
          :size="48"
          :mood="isLatestAssistant ? (avatarMood || 'idle') : 'idle'"
          :expression="isLatestAssistant ? (avatarExpr || 'neutre') : 'neutre'"
        />
        <span class="text-sm font-medium text-[var(--text-primary)]">Study Copilot</span>
      </div>

      <div class="pl-0 min-w-0">
        <!-- Thinking indicator -->
        <div v-if="message.isStreaming && !message.content" class="flex items-center gap-1.5 py-1.5" aria-label="思考中">
          <span class="thinking-dot"></span>
          <span class="thinking-dot" style="animation-delay: 0.15s"></span>
          <span class="thinking-dot" style="animation-delay: 0.3s"></span>
        </div>

        <!-- Thinking steps -->
        <details
          v-else-if="Array.isArray(message.thinking) && message.thinking.length > 0"
          class="thinking-section mb-3"
        >
          <summary
            class="thinking-summary text-xs text-[var(--text-muted)] cursor-pointer select-none flex items-center gap-1.5 list-none py-1 hover:text-[var(--text-secondary)]"
          >
            <el-icon class="w-3.5 h-3.5 transition-transform duration-200">
              <ArrowRight />
            </el-icon>
            思考过程 ({{ message.thinking.length }} 步)
          </summary>
          <div
            v-for="(t, ti) in message.thinking"
            :key="ti"
            class="flex items-start gap-2 py-1 text-xs text-[var(--text-muted)]"
          >
            <span class="font-medium text-[var(--text-secondary)] flex-shrink-0">{{ String(t.step) }}.</span>
            <span class="leading-relaxed">{{ t.detail }}</span>
          </div>
        </details>

        <!-- Answer body -->
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
import { ArrowRight, DocumentCopy } from '@/components/icons'
import type { ChatStreamMessage } from '@/stores/chat'
import type { BotMood } from '@/components/CopilotBotAvatar.vue'
import type { ExpressionId } from '@/bot/expressions'
import CopilotBotAvatar from '@/components/CopilotBotAvatar.vue'
import TTSPlayer from '@/components/TTSPlayer.vue'
import ChatSourceCards from './ChatSourceCards.vue'

defineProps<{
  message: ChatStreamMessage
  renderedMarkdown?: string
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
</script>
