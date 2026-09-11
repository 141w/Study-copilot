<template>
  <div class="chat-input-wrapper w-full">
    <div class="flex gap-2.5 sm:gap-3 items-center w-full">
      <!-- Input container (standard clean rounded-lg rectangle, not capsule) -->
      <div
        class="flex-1 bg-[var(--surface-card)] border border-[var(--border-default)] hover:border-[var(--color-primary-light)] focus-within:border-[var(--color-primary)] focus-within:ring-2 focus-within:ring-[var(--color-primary)]/15 rounded-lg px-3 py-2 shadow-xs transition-all duration-200 flex items-center"
      >
        <textarea
          ref="textareaRef"
          v-model="inputText"
          :placeholder="placeholder"
          :disabled="disabled"
          rows="1"
          class="chat-textarea w-full bg-transparent resize-none border-0 outline-none text-sm leading-normal text-[var(--text-primary)] placeholder-[var(--text-muted)] max-h-32 overflow-y-auto p-0 focus:ring-0 focus:outline-none"
          style="min-height: 20px; height: 20px;"
          @keydown="handleKeyDown"
          @input="adjustHeight"
        ></textarea>
      </div>

      <!-- Action Button (Stop when streaming, Send when idle) -->
      <button
        v-if="loading"
        type="button"
        class="flex items-center justify-center w-9 h-9 rounded-lg text-white bg-rose-600 hover:bg-rose-700 transition-colors shadow-xs cursor-pointer active:scale-95 flex-shrink-0"
        title="停止回答"
        aria-label="停止生成"
        @click="stopStream"
      >
        <svg class="w-4 h-4 fill-current" viewBox="0 0 24 24" aria-hidden="true">
          <rect x="6" y="6" width="12" height="12" rx="2" />
        </svg>
      </button>

      <button
        v-else
        type="button"
        class="flex items-center justify-center w-9 h-9 rounded-lg text-[var(--text-inverse)] bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)] disabled:opacity-30 disabled:cursor-not-allowed transition-all shadow-xs cursor-pointer active:scale-95 flex-shrink-0"
        :disabled="disabled || !inputText.trim()"
        title="发送消息"
        aria-label="发送消息"
        @click="sendMessage"
      >
        <el-icon :size="16"><Promotion /></el-icon>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue'
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

const MIN_HEIGHT_PX = 20
const MAX_HEIGHT_PX = 120
let rafId: number | null = null

function adjustHeight(): void {
  const el = textareaRef.value
  if (!el) return
  if (rafId) cancelAnimationFrame(rafId)
  rafId = requestAnimationFrame(() => {
    const cur = textareaRef.value
    if (!cur) return
    cur.style.height = 'auto'
    const target = Math.min(Math.max(cur.scrollHeight, MIN_HEIGHT_PX), MAX_HEIGHT_PX)
    if (Math.abs(cur.clientHeight - target) <= 1) return
    cur.style.height = target + 'px'
    rafId = null
  })
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
    nextTick(() => {
      if (textareaRef.value) {
        textareaRef.value.style.height = '20px'
      }
    })
  }
}

function stopStream(): void {
  emit('stop')
}

onMounted(() => {
  if (textareaRef.value) {
    textareaRef.value.style.height = '20px'
  }
})
</script>
