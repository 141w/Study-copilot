<template>
  <div class="chat-input-wrapper w-full relative">
    <!-- 5.6 附件行（两阶段状态；仅上传中禁发） -->
    <ChatAttachments
      :attachments="attachments"
      @remove="onRemoveAttachment"
    />

    <!-- 范围胶囊行 -->
    <ScopeChips
      v-model:mention-open="mentionOpen"
      :chips="scopeChips"
      :candidates="mentionCandidates"
      class="relative"
      @remove="removeScope"
      @pick="pickScope"
    />

    <div class="flex gap-2.5 sm:gap-3 items-center w-full mt-1.5">
      <!-- Input container -->
      <div
        class="flex-1 bg-[var(--surface-card)] border border-[var(--border-default)] hover:border-[var(--border-hover)] focus-within:border-[var(--color-primary)] focus-within:ring-2 focus-within:ring-[var(--color-primary-light)] rounded-lg px-3 py-2 transition-all duration-200 flex items-center gap-1.5"
      >
        <button
          type="button"
          class="shrink-0 flex items-center justify-center w-6 h-6 rounded text-[var(--text-muted)] hover:text-[var(--color-primary)] hover:bg-[var(--color-primary)]/10 transition-colors cursor-pointer"
          title="添加附件"
          aria-label="添加附件"
          data-test="attach-btn"
          @click="openFilePicker"
        >
          <el-icon :size="15"><DocumentAdd /></el-icon>
        </button>
        <input
          ref="fileInputRef"
          type="file"
          class="hidden"
          multiple
          accept="image/*,.pdf,.docx,.pptx,.txt,.md"
          data-test="attach-input"
          @change="onFilesSelected"
        />
        <textarea
          ref="textareaRef"
          v-model="inputText"
          :placeholder="placeholder"
          :disabled="disabled"
          rows="1"
          class="chat-textarea w-full bg-transparent resize-none border-0 outline-none text-sm leading-normal text-[var(--text-primary)] placeholder-[var(--text-muted)] max-h-32 overflow-y-auto p-0 focus:ring-0 focus:outline-none"
          style="min-height: 20px; height: 20px;"
          @keydown="handleKeyDown"
          @input="handleInput"
          @compositionstart="onCompositionStart"
          @compositionend="onCompositionEnd"
        ></textarea>
      </div>

      <ModelChip :models="modelOptions" class="shrink-0" />

      <!-- Action Button (Stop when streaming, Send when idle) -->
      <button
        v-if="loading"
        type="button"
        class="flex items-center justify-center w-9 h-9 rounded-lg text-[var(--text-inverse)] bg-[var(--color-error)] hover:bg-[var(--color-error)]/90 transition-colors cursor-pointer active:scale-95 flex-shrink-0"
        title="停止回答"
        aria-label="停止生成"
        data-test="stop-btn"
        @click="stopStream"
      >
        <svg class="w-4 h-4 fill-current" viewBox="0 0 24 24" aria-hidden="true">
          <rect x="6" y="6" width="12" height="12" rx="2" />
        </svg>
      </button>

      <button
        v-else
        type="button"
        class="send-btn flex items-center justify-center w-9 h-9 rounded-lg text-[var(--text-inverse)] bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)] disabled:opacity-30 disabled:cursor-not-allowed transition-all cursor-pointer active:scale-95 flex-shrink-0"
        :disabled="sendDisabled"
        title="发送消息"
        aria-label="发送消息"
        data-test="send-btn"
        @click="sendMessage"
      >
        <el-icon :size="16"><Promotion /></el-icon>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { DocumentAdd, Promotion } from '@/components/icons'
import ScopeChips, { type ScopeChip } from './ScopeChips.vue'
import ModelChip from './ModelChip.vue'
import ChatAttachments, { type ChatAttachmentItem } from './ChatAttachments.vue'
import { useDocumentStore } from '@/stores/document'
import { useCourseStore } from '@/stores/course'

const props = withDefaults(defineProps<{
  loading?: boolean
  disabled?: boolean
  placeholder?: string
  scopeChips?: ScopeChip[]
  attachments?: ChatAttachmentItem[]
}>(), {
  loading: false,
  disabled: false,
  placeholder: '输入您的问题...',
  scopeChips: () => [],
  attachments: () => [],
})

const emit = defineEmits<{
  send: [content: string]
  stop: []
  'remove-scope': [chip: ScopeChip]
  'add-scope': [chip: ScopeChip]
  /** 5.6: 用户选择本地文件，由父级负责上传与两阶段状态 */
  'add-attachments': [files: File[]]
  'remove-attachment': [id: string]
}>()

const inputText = ref('')
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const isComposing = ref(false)
const mentionOpen = ref(false)
const documentStore = useDocumentStore()
const courseStore = useCourseStore()

/** 5.6 硬性语义：仅「上传中」禁发；解析可后台继续 */
const hasUploading = computed(() =>
  (props.attachments || []).some(a => a.status === 'uploading')
)
const sendDisabled = computed(
  () => props.disabled || !inputText.value.trim() || hasUploading.value
)

const modelOptions = computed(() => {
  // 暂用已配置模型 + 常见上下文档位（详细列表在模型配置页）
  const name = (localStorage.getItem('study-copilot.chat-model') || 'default') as string
  return [
    { id: name || 'default', label: name === 'default' ? '默认模型' : name, contextWindow: 0 },
  ]
})

const mentionCandidates = computed<ScopeChip[]>(() => {
  const docs = (documentStore.documents || []).map(d => ({
    key: `doc:${d.id}`,
    kind: 'doc' as const,
    id: d.id,
    label: d.filename,
  }))
  const courses = (courseStore.courses || []).map(c => ({
    key: `course:${c.id}`,
    kind: 'course' as const,
    id: c.id,
    label: c.name,
  }))
  return [...docs, ...courses]
})

const MIN_HEIGHT_PX = 20
const MAX_HEIGHT_PX = 120
let rafId: number | null = null
let mentionQuery = ''

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

function onCompositionStart(): void {
  isComposing.value = true
}

function onCompositionEnd(): void {
  isComposing.value = false
  handleInput()
}

function handleInput(): void {
  adjustHeight()
  // @ 唤起：必须等输入法组合结束，避免中文输入误弹
  if (isComposing.value) return
  const text = inputText.value
  const at = text.lastIndexOf('@')
  if (at >= 0) {
    const after = text.slice(at + 1)
    if (!/[\s\n]/.test(after) && after.length <= 20) {
      mentionOpen.value = true
      mentionQuery = after
      return
    }
  }
  mentionOpen.value = false
  mentionQuery = ''
}

function handleKeyDown(event: KeyboardEvent): void {
  if (event.isComposing || isComposing.value) return

  if (mentionOpen.value) {
    const chipsRef = document.querySelector('[data-test="scope-chips"]') as any
    // 上下选择交给 ScopeChips 的 expose 经自定义事件也可；此处简单处理
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      return
    }
    if (event.key === 'Enter') {
      event.preventDefault()
      return
    }
    if (event.key === 'Escape') {
      event.preventDefault()
      mentionOpen.value = false
      return
    }
    void chipsRef
  }

  if (event.key === 'Backspace' && !inputText.value && props.scopeChips.length) {
    event.preventDefault()
    emit('remove-scope', props.scopeChips[props.scopeChips.length - 1])
    return
  }

  if (event.key === 'Enter') {
    if (event.shiftKey) {
      nextTick(adjustHeight)
      return
    }
    event.preventDefault()
    sendMessage()
  }
}

function sendMessage(): void {
  if (inputText.value.trim() && !props.disabled && !props.loading && !hasUploading.value) {
    emit('send', inputText.value.trim())
    inputText.value = ''
    mentionOpen.value = false
    nextTick(() => {
      if (textareaRef.value) {
        textareaRef.value.style.height = '20px'
      }
    })
  }
}

function openFilePicker(): void {
  fileInputRef.value?.click()
}

function onFilesSelected(event: Event): void {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  if (files.length) {
    emit('add-attachments', files)
  }
  input.value = ''
}

function onRemoveAttachment(id: string): void {
  emit('remove-attachment', id)
}

function stopStream(): void {
  // 停止 = 中断流；chat store AbortError 分支已保留部分回答
  emit('stop')
}

function removeScope(chip: ScopeChip): void {
  emit('remove-scope', chip)
}

function pickScope(chip: ScopeChip): void {
  emit('add-scope', chip)
  // 去掉光标处的 @query
  const text = inputText.value
  const at = text.lastIndexOf('@')
  if (at >= 0) {
    inputText.value = text.slice(0, at)
    mentionOpen.value = false
    mentionQuery = ''
  }
}

onMounted(() => {
  if (textareaRef.value) {
    textareaRef.value.style.height = '20px'
  }
  documentStore.fetchDocuments().catch(() => {})
  courseStore.fetchCourses().catch(() => {})
})

defineExpose({ mentionQuery: () => mentionQuery })
</script>

<style scoped>
.send-btn :deep(svg) {
  color: inherit;
}
</style>