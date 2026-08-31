<template>
  <div ref="editorContainer" class="note-editor">
    <!-- Toolbar -->
    <div class="flex items-center justify-between px-4 py-2 border-b border-[var(--border-default)] bg-[var(--bg-secondary)] rounded-t-lg">
      <div class="flex items-center gap-1">
        <el-button circle size="small" @click="insertMarkdown('**', '**')" title="粗体">
          <el-icon class="font-bold text-xs">B</el-icon>
        </el-button>
        <el-button circle size="small" @click="insertMarkdown('*', '*')" title="斜体">
          <el-icon class="italic text-xs">I</el-icon>
        </el-button>
        <el-button circle size="small" @click="insertLinePrefix('## ')" title="标题">
          <span class="text-xs font-bold">H</span>
        </el-button>
        <el-button circle size="small" @click="insertLinePrefix('- ')" title="列表">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16" />
          </svg>
        </el-button>
        <el-button circle size="small" @click="insertMarkdown('`', '`')" title="代码">
          <span class="text-xs font-mono">&lt;/&gt;</span>
        </el-button>
        <el-button circle size="small" @click="insertLinePrefix('> ')" title="引用">
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <path d="M6 17h3l2-4V7H5v6h3zm8 0h3l2-4V7h-6v6h3z" />
          </svg>
        </el-button>
        <div class="w-px h-5 bg-[var(--bg-active)] mx-1"></div>
        <el-button circle size="small" @click="togglePreview" :type="showPreview ? 'primary' : 'default'" title="预览">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
          </svg>
        </el-button>
        <el-button circle size="small" @click="openTransform" title="AI 内容转换">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
          </svg>
        </el-button>
      </div>
      <div class="flex items-center gap-2">
        <span class="text-xs text-[var(--text-muted)]">{{ charCount }} 字</span>
      </div>
    </div>

    <!-- Title Input -->
    <el-input
      v-model="localTitle"
      type="text"
      placeholder="笔记标题..."
      class="title-input"
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
    <div v-if="showPreview" class="preview-area" v-html="renderedContent"></div>
    <el-input
      v-else
      ref="textareaEl"
      v-model="localContent"
      type="textarea"
      placeholder="开始记录笔记...支持 Markdown 语法"
      class="editor-textarea"
      :autosize="{ minRows: 10, maxRows: 20 }"
      @input="onContentChange"
      @keydown.tab.prevent="handleTab"
    />

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
  let html = localContent.value
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$2</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code class="inline-code">$1</code>')
    .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" class="text-blue-600 underline" target="_blank">$1</a>')
    .replace(/\n/g, '<br>')
  return html
})

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
  const textarea = textareaEl.value?.textareaEl
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
  const textarea = textareaEl.value?.textareaEl
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
  const textarea = textareaEl.value?.textareaEl
  if (!textarea) return

  const start = textarea.selectionStart
  const end = textarea.selectionEnd

  localContent.value =
    localContent.value.substring(0, start) +
    '  ' +
    localContent.value.substring(end)

  nextTick(() => {
    textarea.focus()
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
  background-color: var(--surface-card);
  border: 1px solid var(--border-default);
  border-radius: 8px;
}

.title-input :deep(.el-input__wrapper) {
  border-radius: 0;
  border-bottom: 1px solid var(--border-default);
  padding: 12px 16px;
  box-shadow: none;
}

.title-input :deep(.el-input__inner) {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text-primary);
}

.title-input :deep(.el-input__inner::placeholder) {
  color: var(--text-muted);
}

.editor-textarea :deep(.el-textarea__inner) {
  border: none;
  border-radius: 0;
  padding: 16px;
  min-height: 300px;
  max-height: 60vh;
  color: var(--text-primary);
  line-height: 1.6;
  resize: none;
  font-family: monospace;
  font-size: 0.875rem;
}

.editor-textarea :deep(.el-textarea__inner::placeholder) {
  color: var(--text-muted);
}

.preview-area {
  padding: 16px;
  min-height: 300px;
  max-height: 60vh;
  overflow-y: auto;
}

.preview-area :deep(h1) {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 1rem 0 0.5rem;
}

.preview-area :deep(h2) {
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0.75rem 0 0.5rem;
}

.preview-area :deep(h3) {
  font-size: 1.125rem;
  font-weight: 500;
  color: var(--text-primary);
  margin: 0.5rem 0 0.25rem;
}

.preview-area :deep(li) {
  list-style: disc;
  margin-left: 1rem;
}

.preview-area :deep(.inline-code) {
  background-color: var(--bg-tertiary);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.875rem;
}

.preview-area :deep(blockquote) {
  padding-left: 1rem;
  border-left: 4px solid var(--border-default);
  color: var(--text-secondary);
  font-style: italic;
}
</style>
