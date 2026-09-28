<template>
  <div class="answers-input w-full relative">
    <!-- 富文本输入大容器 (复刻 WeKnora rich-input-container 规范) -->
    <div
      class="rich-input-container relative w-full bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-2xl transition-all duration-200 shadow-sm hover:shadow-md focus-within:border-[var(--color-primary)] focus-within:shadow-[0_4px_20px_rgba(16,185,129,0.12)]"
      data-guide="chat-input"
    >
      <!-- 附件行 (5.6 临时附件) -->
      <ChatAttachments
        v-if="attachments.length > 0"
        :attachments="attachments"
        class="px-3 pt-2"
        @remove="onRemoveAttachment"
      />

      <!-- 选中的范围胶囊行 (复刻 WeKnora selected-tags-inline) -->
      <ScopeChips
        ref="scopeChipsRef"
        v-model:mention-open="mentionOpen"
        :chips="scopeChips"
        :candidates="mentionCandidates"
        @remove="removeScope"
        @pick="pickScope"
      />

      <!-- 实际多行自适应输入框 (复刻 WeKnora t-textarea autosize 规范) -->
      <div class="textarea-wrapper px-3.5 pt-2.5 pb-12">
        <textarea
          ref="textareaRef"
          v-model="inputText"
          :placeholder="dynamicPlaceholder"
          :disabled="disabled"
          rows="2"
          class="chat-textarea w-full bg-transparent resize-none border-0 outline-none text-[14.5px] leading-relaxed text-[var(--text-primary)] placeholder-[var(--text-muted)] max-h-48 overflow-y-auto p-0 focus:ring-0 focus:outline-none scrollbar-thin"
          @keydown="handleKeyDown"
          @input="handleInput"
          @compositionstart="onCompositionStart"
          @compositionend="onCompositionEnd"
        ></textarea>
      </div>

      <!-- 隐藏的文件选择器 -->
      <input
        ref="fileInputRef"
        type="file"
        class="hidden"
        multiple
        accept="image/*,.pdf,.docx,.pptx,.txt,.md"
        data-test="attach-input"
        @change="onFilesSelected"
      />

      <!-- 底部内嵌控制栏 (复刻 WeKnora control-bar 规范) -->
      <div class="control-bar absolute bottom-2.5 left-3 right-3 flex items-center justify-between gap-2 pointer-events-auto">
        <!-- 左侧工具组 -->
        <div class="control-left flex items-center gap-1.5 min-w-0 flex-1">
          <!-- @ 范围/知识库选择按钮 (带已选数量角标) -->
          <button
            type="button"
            class="control-btn kb-btn relative inline-flex items-center justify-center w-7 h-7 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition-colors cursor-pointer"
            :class="{ 'is-active text-[var(--color-primary)] bg-[var(--color-primary-light)]': scopeChips.length > 0 }"
            title="选择参考课程或文档范围 (@)"
            aria-label="选择参考范围"
            data-guide="chat-kb-mention"
            @click.stop="triggerMentionButton"
          >
            <svg class="w-4 h-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8">
              <circle cx="10" cy="10" r="3.5" />
              <path d="M13.5 10V11.5C13.5 12.163 13.7634 12.7989 14.2322 13.2678C14.7011 13.7366 15.337 14 16 14C16.663 14 17.2989 13.7366 17.7678 13.2678C18.2366 12.7989 18.5 12.163 18.5 11.5V10C18.5 7.74566 17.6045 5.58365 16.0104 3.98959C14.4163 2.39553 12.2543 1.5 10 1.5C7.74566 1.5 5.58365 2.39553 3.98959 3.98959C2.39553 5.58365 1.5 7.74566 1.5 10C1.5 12.2543 2.39553 14.4163 3.98959 16.0104C5.58365 17.6045 7.74566 18.5 10 18.5H12" />
            </svg>
            <span
              v-if="scopeChips.length > 0"
              class="absolute -top-1 -right-1 min-w-[15px] h-[15px] px-1 rounded-full bg-[var(--color-primary)] text-[var(--text-inverse)] text-[9px] font-bold flex items-center justify-center border-2 border-[var(--bg-primary)] leading-none"
            >{{ scopeChips.length }}</span>
          </button>

          <!-- 附件上传按钮 (带文件数角标) -->
          <button
            type="button"
            class="control-btn attach-btn relative inline-flex items-center justify-center w-7 h-7 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition-colors cursor-pointer"
            :class="{ 'is-active text-[var(--color-primary)] bg-[var(--color-primary-light)]': attachments.length > 0 }"
            title="添加图片或文档附件"
            aria-label="添加附件"
            data-test="attach-btn"
            @click="openFilePicker"
          >
            <!-- 回形针图标 -->
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
            </svg>
            <span
              v-if="attachments.length > 0"
              class="absolute -top-1 -right-1 min-w-[15px] h-[15px] px-1 rounded-full bg-[var(--color-primary)] text-[var(--text-inverse)] text-[9px] font-bold flex items-center justify-center border-2 border-[var(--bg-primary)] leading-none"
            >{{ attachments.length }}</span>
          </button>

          <!-- 模型选择胶囊 (真接线与精致浮层，复刻 WeKnora model-selector-trigger) -->
          <ModelChip
            :models="modelOptions"
            class="shrink-0"
            @select="onModelSelect"
          />
        </div>

        <!-- 右侧操作区 (发送 / 停止生成) -->
        <div class="control-right flex items-center gap-1.5 shrink-0">
          <!-- 停止生成按钮 (生成中呼吸动效，复刻 WeKnora stop-btn 规范) -->
          <button
            v-if="loading"
            type="button"
            class="stop-btn flex items-center justify-center w-8 h-8 rounded-lg text-rose-500 bg-rose-50 hover:bg-rose-100 border border-rose-200 transition-all cursor-pointer active:scale-95 dark:bg-rose-950/30 dark:border-rose-900/50 dark:hover:bg-rose-950/50"
            title="停止生成"
            aria-label="停止生成"
            data-test="stop-btn"
            @click="stopStream"
          >
            <!-- 呼吸小方块 SVG -->
            <svg class="w-3.5 h-3.5 text-rose-500 animate-pulse" viewBox="0 0 24 24" fill="currentColor">
              <rect x="5" y="5" width="14" height="14" rx="2" />
            </svg>
          </button>

          <!-- 发送按钮 (复刻 WeKnora send-btn 规范) -->
          <button
            v-else
            type="button"
            class="send-btn flex items-center justify-center w-8 h-8 rounded-lg text-[var(--text-inverse)] bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)] disabled:opacity-35 disabled:cursor-not-allowed transition-all cursor-pointer active:scale-95 shadow-sm"
            :disabled="sendDisabled"
            title="发送消息 (Enter 发送，Shift+Enter 换行)"
            aria-label="发送消息"
            data-test="send-btn"
            data-guide="chat-send"
            @click="sendMessage"
          >
            <!-- 纸飞机矢量图标 -->
            <svg class="w-4 h-4 transform translate-x-px -translate-y-px" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import ScopeChips, { type ScopeChip } from './ScopeChips.vue'
import ModelChip from './ModelChip.vue'
import ChatAttachments, { type ChatAttachmentItem } from './ChatAttachments.vue'
import { useDocumentStore } from '@/stores/document'
import { useCourseStore } from '@/stores/course'

const props = withDefaults(
  defineProps<{
    loading?: boolean
    disabled?: boolean
    placeholder?: string
    scopeChips?: ScopeChip[]
    attachments?: ChatAttachmentItem[]
  }>(),
  {
    loading: false,
    disabled: false,
    placeholder: '输入您的问题...',
    scopeChips: () => [],
    attachments: () => [],
  }
)

const emit = defineEmits<{
  send: [content: string, modelOverride?: string]
  stop: []
  'remove-scope': [chip: ScopeChip]
  'add-scope': [chip: ScopeChip]
  'add-attachments': [files: File[]]
  'remove-attachment': [id: string]
  'model-change': [modelId: string]
}>()

const inputText = ref('')
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const scopeChipsRef = ref<InstanceType<typeof ScopeChips> | null>(null)
const isComposing = ref(false)
const mentionOpen = ref(false)
const selectedModelOverride = ref<string>('')
const documentStore = useDocumentStore()
const courseStore = useCourseStore()

// 仅「上传中」禁发；解析可后台继续 (5.6 规范)
const hasUploading = computed(() =>
  (props.attachments || []).some(a => a.status === 'uploading')
)
const sendDisabled = computed(
  () => props.disabled || !inputText.value.trim() || hasUploading.value
)

const dynamicPlaceholder = computed(() => {
  if (props.scopeChips.length > 0) {
    return `基于已选的 ${props.scopeChips.length} 项范围提问...`
  }
  return props.placeholder || '输入您的问题... (输入 @ 可选择课程或文档范围)'
})

const modelOptions = computed(() => {
  const currentSaved = (localStorage.getItem('study-copilot.chat-model') || '') as string
  return [
    { id: currentSaved || 'default', label: currentSaved ? currentSaved : '默认主模型', contextWindow: 131072 },
  ]
})

const mentionCandidates = computed<ScopeChip[]>(() => {
  const courseList = Array.isArray(courseStore.courses) ? courseStore.courses : []
  const courses = courseList.map(c => ({
    key: `course:${c.id}`,
    kind: 'course' as const,
    id: String(c.id),
    label: c.name,
  }))
  const rawDocs = Array.isArray(documentStore.readyDocuments) && documentStore.readyDocuments.length
    ? documentStore.readyDocuments
    : (Array.isArray(documentStore.documents) ? documentStore.documents : [])
  const docs = rawDocs.map(d => ({
    key: `doc:${d.id}`,
    kind: 'doc' as const,
    id: String(d.id),
    label: d.filename,
  }))
  return [...courses, ...docs]
})

function onModelSelect(modelId: string): void {
  selectedModelOverride.value = modelId
  emit('model-change', modelId)
}

function autoResize(): void {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(Math.max(el.scrollHeight, 40), 200)}px`
}

function handleInput(_e?: Event): void {
  autoResize()
  if (isComposing.value) return
  const val = inputText.value
  const atIdx = val.lastIndexOf('@')
  if (atIdx !== -1 && atIdx === val.length - 1) {
    mentionOpen.value = true
    scopeChipsRef.value?.setQuery('')
  } else if (mentionOpen.value && atIdx !== -1) {
    scopeChipsRef.value?.setQuery(val.slice(atIdx + 1))
  } else if (mentionOpen.value) {
    mentionOpen.value = false
  }
}

function handleKeyDown(e: KeyboardEvent): void {
  if (isComposing.value || e.isComposing) return

  // 1. 弹层打开时的上下箭头与 Enter 导航
  if (mentionOpen.value) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      scopeChipsRef.value?.move(1)
      return
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      scopeChipsRef.value?.move(-1)
      return
    }
    if (e.key === 'Enter') {
      e.preventDefault()
      scopeChipsRef.value?.selectCurrent()
      return
    }
    if (e.key === 'Escape') {
      mentionOpen.value = false
      return
    }
  }

  // 2. 空文本按 Backspace 弹出移除最后一个胶囊 (5.1 规范)
  if (e.key === 'Backspace' && !inputText.value && props.scopeChips.length > 0) {
    e.preventDefault()
    const last = props.scopeChips[props.scopeChips.length - 1]
    emit('remove-scope', last)
    return
  }

  // 3. Enter 发送消息 (Shift+Enter 换行)
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

function onCompositionStart(): void {
  isComposing.value = true
}

function onCompositionEnd(e: CompositionEvent): void {
  isComposing.value = false
  handleInput(e)
}

function triggerMentionButton(): void {
  mentionOpen.value = !mentionOpen.value
  if (mentionOpen.value) {
    scopeChipsRef.value?.setQuery('')
    nextTick(() => textareaRef.value?.focus())
  }
}

function removeScope(chip: ScopeChip): void {
  emit('remove-scope', chip)
}

function pickScope(chip: ScopeChip): void {
  emit('add-scope', chip)
  // 如果输入框中有 '@'，只清除从 '@' 开始的 mention 标识，保留用户前后输入的问题文本
  const val = inputText.value
  const atIdx = val.lastIndexOf('@')
  if (atIdx !== -1) {
    const afterAt = val.slice(atIdx)
    const spaceOffset = afterAt.search(/\s/)
    if (spaceOffset === -1) {
      const before = val.slice(0, atIdx).trimEnd()
      inputText.value = before ? `${before} ` : ''
    } else {
      const before = val.slice(0, atIdx).trimEnd()
      const after = afterAt.slice(spaceOffset).trimStart()
      inputText.value = before ? `${before} ${after}` : after
    }
  }
  mentionOpen.value = false
  nextTick(() => textareaRef.value?.focus())
}

function openFilePicker(): void {
  fileInputRef.value?.click()
}

function onFilesSelected(e: Event): void {
  const files = (e.target as HTMLInputElement).files
  if (!files || !files.length) return
  emit('add-attachments', Array.from(files))
  if (fileInputRef.value) fileInputRef.value.value = ''
}

function onRemoveAttachment(id: string): void {
  emit('remove-attachment', id)
}

function stopStream(): void {
  emit('stop')
}

function sendMessage(): void {
  if (sendDisabled.value) return
  const text = inputText.value.trim()
  if (!text) return
  if (selectedModelOverride.value) {
    emit('send', text, selectedModelOverride.value)
  } else {
    emit('send', text)
  }
  inputText.value = ''
  nextTick(() => {
    if (textareaRef.value) {
      textareaRef.value.style.height = 'auto'
      textareaRef.value.focus()
    }
  })
}

onMounted(() => {
  autoResize()
  courseStore.fetchCourses().catch(() => {})
})
</script>

<style scoped>
/* 滚动条轻量样式 */
.scrollbar-thin::-webkit-scrollbar {
  width: 4px;
}
.scrollbar-thin::-webkit-scrollbar-thumb {
  background-color: var(--border-default, #e5e7eb);
  border-radius: 9999px;
}
</style>