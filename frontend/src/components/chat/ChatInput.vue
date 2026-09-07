<template>
  <div class="chat-input-wrapper w-full">
    <div
      class="chat-input-card relative bg-[var(--surface-card)] border border-[var(--border-default)] hover:border-[var(--color-primary-light)] focus-within:border-[var(--color-primary)] focus-within:ring-2 focus-within:ring-[var(--color-primary)]/15 rounded-2xl p-2.5 sm:p-3 shadow-xs transition-all duration-200"
    >
      <!-- Multi-line auto-resizing textarea -->
      <textarea
        ref="textareaRef"
        v-model="inputText"
        :placeholder="placeholder"
        :disabled="disabled"
        rows="1"
        class="chat-textarea w-full bg-transparent resize-none border-0 outline-none text-sm leading-relaxed text-[var(--text-primary)] placeholder-[var(--text-muted)] max-h-36 overflow-y-auto px-1.5 pt-0.5 pb-1 focus:ring-0 focus:outline-none"
        @keydown="handleKeyDown"
        @input="adjustHeight"
      ></textarea>

      <!-- Bottom toolbar: Hint on the left, Action button on the right -->
      <div class="flex items-center justify-between pt-2 border-t border-[var(--border-default)]/40 mt-1 px-1">
        <!-- Keyboard hint -->
        <div class="flex items-center gap-2 text-[11px] text-[var(--text-muted)] select-none">
          <span class="sm:hidden">Enter 发送</span>
        </div>

        <!-- Action Button (Stop when streaming, Send when idle) -->
        <div class="flex items-center gap-1.5">
          <button
            v-if="loading"
            type="button"
            class="flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium text-rose-600 bg-rose-50 hover:bg-rose-100 dark:text-rose-400 dark:bg-rose-950/40 dark:hover:bg-rose-950/60 border border-rose-200 dark:border-rose-800/40 transition-colors shadow-xs cursor-pointer active:scale-95"
            title="停止生成"
            aria-label="停止生成"
            @click="stopStream"
          >
            <span class="w-2 h-2 rounded-xs bg-rose-500 animate-pulse"></span>
            <span>停止生成</span>
          </button>

          <button
            v-else
            type="button"
            class="flex items-center justify-center w-8 h-8 rounded-full text-white bg-[var(--color-primary)] hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-xs cursor-pointer active:scale-95"
            :disabled="disabled || !inputText.trim()"
            title="发送消息"
            aria-label="发送消息"
            @click="sendMessage"
          >
            <el-icon :size="15"><Promotion /></el-icon>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { Promotion } from '@/components/icons'

const props = withDefaults(defineProps<{
  loading?: boolean
  disabled?: boolean
  placeholder?: string
}>(), {
  loading: false,
  disabled: false,
  placeholder: '输入您的问题...'
})

const emit = defineEmits<{
  send: [content: string]
  stop: []
}>()

const inputText = ref('')
const textareaRef = ref<HTMLTextAreaElement | null>(null)

function adjustHeight(): void {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 144) + 'px'
}

function handleKeyDown(event: KeyboardEvent): void {
  if (event.key === 'Enter') {
    if (event.shiftKey) {
      // Shift+Enter 允许换行，自动撑开高度
      nextTick(adjustHeight)
      return
    }
    // Enter 发送（中文输入法组合阶段不发送）
    if (event.isComposing) return
    event.preventDefault()
    sendMessage()
  }
}

function sendMessage(): void {
  if (inputText.value.trim() && !props.disabled && !props.loading) {
    emit('send', inputText.value.trim())
    inputText.value = ''
    nextTick(adjustHeight)
  }
}

function stopStream(): void {
  emit('stop')
}
</script>
