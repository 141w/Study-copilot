<template>
  <div ref="editorContainer" class="note-editor">
    <!-- Toolbar -->
    <div class="flex items-center justify-between px-4 py-2 border-b border-[var(--border-default)] bg-[var(--bg-secondary)] rounded-t-lg">
      <div class="flex items-center gap-1">
        <button
          @click="insertMarkdown('**', '**')"
          class="p-1.5 text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-active)] rounded transition-colors"
          title="粗体"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 4h8a4 4 0 014 4 4 4 0 01-4 4H6z M6 12h9a4 4 0 014 4 4 4 0 01-4 4H6z" />
          </svg>
        </button>
        <button
          @click="insertMarkdown('*', '*')"
          class="p-1.5 text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-active)] rounded transition-colors"
          title="斜体"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 4h4m-2 0l-4 16m2-16l4 16" />
          </svg>
        </button>
        <button
          @click="insertLinePrefix('## ')"
          class="p-1.5 text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-active)] rounded transition-colors text-xs font-bold"
          title="标题"
        >
          H
        </button>
        <button
          @click="insertLinePrefix('- ')"
          class="p-1.5 text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-active)] rounded transition-colors"
          title="列表"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16" />
          </svg>
        </button>
        <button
          @click="insertMarkdown('`', '`')"
          class="p-1.5 text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-active)] rounded transition-colors text-xs font-mono"
          title="代码"
        >
          &lt;/&gt;
        </button>
        <button
          @click="insertLinePrefix('> ')"
          class="p-1.5 text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-active)] rounded transition-colors"
          title="引用"
        >
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <path d="M6 17h3l2-4V7H5v6h3zm8 0h3l2-4V7h-6v6h3z" />
          </svg>
        </button>
        <div class="w-px h-5 bg-[var(--bg-active)] mx-1"></div>
        <button
          @click="togglePreview"
          class="p-1.5 rounded transition-colors text-xs font-medium"
          :class="showPreview ? 'text-[var(--color-primary)] bg-[var(--bg-active)]' : 'text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-active)]'"
          title="预览"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
          </svg>
        </button>
        <button
          @click="openTransform"
          class="p-1.5 text-[var(--text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-accent-light, #f3f0ff)] rounded transition-colors"
          title="AI 内容转换"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
          </svg>
        </button>
      </div>
      <div class="flex items-center gap-2">
        <span class="text-xs text-[var(--text-muted)]">{{ charCount }} 字</span>
      </div>
    </div>

    <!-- Title Input -->
    <input
      v-model="localTitle"
      type="text"
      placeholder="笔记标题..."
      class="w-full px-4 py-3 border-b border-[var(--border-default)] text-lg font-medium text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none"
      @input="onTitleChange"
    />

    <!-- Tags Input -->
    <div class="px-4 py-2 border-b border-[var(--border-default)] flex items-center gap-2 flex-wrap">
      <span
        v-for="tag in localTags"
        :key="tag"
        class="text-xs px-2 py-0.5 bg-[var(--bg-tertiary)] text-[var(--text-secondary)] rounded-full flex items-center gap-1"
      >
        {{ tag }}
        <button @click="removeTag(tag)" class="text-[var(--text-muted)] hover:text-[var(--text-secondary)]">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </span>
      <input
        v-model="newTag"
        type="text"
        placeholder="添加标签..."
        class="text-xs border-none outline-none bg-transparent w-20 placeholder-[var(--text-muted)]"
        @keydown.enter.prevent="addTag"
      />
    </div>

    <!-- Editor / Preview Area -->
    <div v-if="showPreview" class="p-4 min-h-[300px] max-h-[60vh] overflow-y-auto prose prose-sm" v-html="renderedContent"></div>
    <textarea
      v-else
      ref="textareaEl"
      v-model="localContent"
      placeholder="开始记录笔记...支持 Markdown 语法"
      class="w-full p-4 min-h-[300px] max-h-[60vh] overflow-y-auto text-[var(--text-primary)] leading-relaxed resize-none focus:outline-none placeholder-[var(--text-muted)] font-mono text-sm"
      @input="onContentChange"
      @keydown.tab.prevent="handleTab"
    ></textarea>

    <!-- Transform Dialog -->
    <TransformDialog
      v-model:visible="showTransformDialog"
      :source-text="localContent"
      :source-title="localTitle"
      :note-id="noteId"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import TransformDialog from './TransformDialog.vue'

const props = defineProps({
  title: { type: String, default: '' },
  content: { type: String, default: '' },
  tags: { type: Array, default: () => [] },
  noteId: { type: String, default: null }
})

const emit = defineEmits(['update:title', 'update:content', 'update:tags', 'save'])

const editorContainer = ref(null)
const textareaEl = ref(null)
const showPreview = ref(false)
const newTag = ref('')
const localTitle = ref(props.title)
const localContent = ref(props.content)
const localTags = ref([...props.tags])

// Transform dialog
const showTransformDialog = ref(false)

const charCount = computed(() => localContent.value.length)

const renderedContent = computed(() => {
  // Simple markdown rendering (no external dependency)
  let html = localContent.value
    // Headers
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    // Bold
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // Italic
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Inline code
    .replace(/`(.+?)`/g, '<code class="bg-[var(--bg-tertiary)] px-1 py-0.5 rounded text-sm">$1</code>')
    // Blockquote
    .replace(/^> (.+)$/gm, '<blockquote class="pl-4 border-l-4 border-[var(--border-default)] text-[var(--text-secondary)] italic">$1</blockquote>')
    // Unordered list items
    .replace(/^- (.+)$/gm, '<li class="ml-4">$1</li>')
    // Links
    .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" class="text-blue-600 underline" target="_blank">$1</a>')
    // Line breaks
    .replace(/\n/g, '<br>')
  return html
})

// Sync props
watch(() => props.title, (val) => { localTitle.value = val })
watch(() => props.content, (val) => { localContent.value = val })
watch(() => props.tags, (val) => { localTags.value = [...val] })

function onTitleChange() {
  emit('update:title', localTitle.value)
  emit('save')
}

function onContentChange() {
  emit('update:content', localContent.value)
  emit('save')
}

function addTag() {
  const tag = newTag.value.trim()
  if (tag && !localTags.value.includes(tag)) {
    localTags.value.push(tag)
    emit('update:tags', [...localTags.value])
    emit('save')
  }
  newTag.value = ''
}

function removeTag(tag) {
  localTags.value = localTags.value.filter(t => t !== tag)
  emit('update:tags', [...localTags.value])
  emit('save')
}

function togglePreview() {
  showPreview.value = !showPreview.value
}

function insertMarkdown(before, after) {
  const textarea = textareaEl.value
  if (!textarea) return

  const start = textarea.selectionStart
  const end = textarea.selectionEnd
  const selected = localContent.value.substring(start, end) || '文本'

  const replacement = before + selected + after
  localContent.value =
    localContent.value.substring(0, start) +
    replacement +
    localContent.value.substring(end)

  nextTick(() => {
    textarea.focus()
    textarea.setSelectionRange(start + before.length, start + before.length + selected.length)
  })

  emit('update:content', localContent.value)
}

function insertLinePrefix(prefix) {
  const textarea = textareaEl.value
  if (!textarea) return

  const start = textarea.selectionStart
  const lineStart = localContent.value.lastIndexOf('\n', start - 1) + 1

  localContent.value =
    localContent.value.substring(0, lineStart) +
    prefix +
    localContent.value.substring(lineStart)

  nextTick(() => {
    textarea.focus()
    textarea.setSelectionRange(start + prefix.length, start + prefix.length)
  })

  emit('update:content', localContent.value)
}

function handleTab(e) {
  const textarea = textareaEl.value
  if (!textarea) return

  const start = textarea.selectionStart
  const end = textarea.selectionEnd

  localContent.value =
    localContent.value.substring(0, start) +
    '  ' +
    localContent.value.substring(end)

  nextTick(() => {
    textarea.setSelectionRange(start + 2, start + 2)
  })

  emit('update:content', localContent.value)
}

function openTransform() {
  showTransformDialog.value = true
}
</script>

<style scoped>
.note-editor {
  @apply bg-[var(--surface-card)] rounded-lg border border-[var(--border-default)];
}

:deep(.prose h1) {
  @apply text-2xl font-bold text-[var(--text-primary)] mb-2 mt-4;
}

:deep(.prose h2) {
  @apply text-xl font-semibold text-[var(--text-primary)] mb-2 mt-3;
}

:deep(.prose h3) {
  @apply text-lg font-medium text-[var(--text-primary)] mb-1 mt-2;
}

:deep(.prose li) {
  @apply list-disc;
}
</style>
