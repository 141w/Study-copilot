<template>
  <!-- 多选标签模式（Chat 风格） -->
  <div v-if="mode === 'multiple'" class="flex items-center gap-2.5 flex-wrap">
    <span class="text-sm text-[var(--text-muted)] font-medium">{{ label }}:</span>
    <button
      v-for="doc in documents"
      :key="doc.id"
      type="button"
      role="checkbox"
      :aria-checked="selectedIds().includes(doc.id)"
      class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium cursor-pointer transition-all duration-150 border select-none outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)]"
      :class="selectedIds().includes(doc.id)
        ? 'bg-[var(--color-primary)] text-[var(--text-inverse)] border-[var(--color-primary)] shadow-sm'
        : 'bg-[var(--surface-card)] border-[var(--border-default)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:border-[var(--border-hover)]'"
      @click="toggleMultiple(doc.id)"
    >
      <svg
        v-if="selectedIds().includes(doc.id)"
        class="w-3.5 h-3.5 shrink-0"
        viewBox="0 0 20 20"
        fill="currentColor"
      >
        <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
      </svg>
      <svg
        v-else
        class="w-3.5 h-3.5 shrink-0 text-[var(--text-muted)]"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
      >
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
      <span class="truncate max-w-[200px]">{{ doc.filename }}</span>
    </button>
    <span v-if="documents.length === 0" class="text-sm text-[var(--text-muted)]">{{ emptyText }}</span>
  </div>

  <!-- 卡片多选模式（Quiz 风格） -->
  <div v-else-if="mode === 'cards'" class="grid grid-cols-2 md:grid-cols-3 gap-2">
    <div
      v-for="doc in documents"
      :key="doc.id"
      role="button"
      tabindex="0"
      :aria-label="`选择文档 ${doc.filename}`"
      class="p-3 border rounded-lg cursor-pointer transition-all"
      :class="selectedIds().includes(doc.id)
        ? 'border-[var(--color-primary)] bg-[var(--color-primary-light)]'
        : 'border-[var(--border-default)]'"
      @click="toggleMultiple(doc.id)"
      @keydown.enter="toggleMultiple(doc.id)"
    >
      <p class="text-sm font-medium text-[var(--text-primary)] truncate">{{ doc.filename }}</p>
      <p class="text-xs text-[var(--text-muted)]">状态: {{ statusText(doc.status) }}</p>
    </div>
    <p v-if="documents.length === 0" class="text-sm text-[var(--text-muted)] col-span-full">{{ emptyText }}</p>
  </div>

  <!-- 单选列表模式（CourseDetail 风格） -->
  <div v-else-if="mode === 'radio'">
    <div v-if="documents.length === 0" class="text-sm text-[var(--text-muted)] py-4 text-center">{{ emptyText }}</div>
    <div v-else class="space-y-2 max-h-64 overflow-y-auto">
      <label
        v-for="doc in documents"
        :key="doc.id"
        class="flex items-center gap-3 p-3 rounded-lg border border-[var(--border-default)] cursor-pointer hover:border-[var(--color-primary)] transition-colors"
        :class="{ 'border-[var(--color-primary)] bg-[var(--color-primary-light)]': modelValue === doc.id }"
      >
        <input
          type="radio"
          :value="doc.id"
          :checked="modelValue === doc.id"
          name="document-picker"
          class="accent-[var(--color-primary)]"
          @change="$emit('update:modelValue', doc.id)"
        />
        <span class="text-sm text-[var(--text-primary)] truncate">{{ doc.filename }}</span>
      </label>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * DocumentPicker（P2-3）：统一文档选择控件。
 *
 * 替代三种平行实现：
 *  - ChatView 的 checkbox 标签列表
 *  - QuizView 的点击卡片网格
 *  - CourseDetailView 的 radio 弹窗列表
 *
 * mode: 'multiple'（标签多选）| 'cards'（卡片多选）| 'radio'（单选）
 */
import type { Document } from '../../types/models'

const props = withDefaults(defineProps<{
  /** multiple/cards: string[]；radio: string | null */
  modelValue: string[] | string | null
  documents: Document[]
  mode?: 'multiple' | 'cards' | 'radio'
  label?: string
  emptyText?: string
}>(), {
  mode: 'multiple',
  label: '参考文档',
  emptyText: '暂无文档，请先上传'
})

const emit = defineEmits<{
  'update:modelValue': [value: string[] | string]
}>()

/** 模板辅助：统一把 modelValue 视为数组（radio 模式不使用） */
function selectedIds(): string[] {
  return Array.isArray(props.modelValue) ? props.modelValue : []
}

function toggleMultiple(docId: string) {
  if (props.mode === 'radio') return
  const current = selectedIds().slice()
  const idx = current.indexOf(docId)
  if (idx > -1) {
    current.splice(idx, 1)
  } else {
    current.push(docId)
  }
  emit('update:modelValue', current)
}

function statusText(status?: string): string {
  const map: Record<string, string> = {
    ready: '已就绪',
    processing: '处理中',
    error: '错误'
  }
  return map[status || ''] || '待处理'
}
</script>
