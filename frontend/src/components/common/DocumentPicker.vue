<template>
  <!-- 多选标签模式（Chat 风格） -->
  <div v-if="mode === 'multiple'" class="flex items-center gap-3 flex-wrap">
    <span class="text-sm text-[var(--text-muted)]">{{ label }}:</span>
    <label
      v-for="doc in documents"
      :key="doc.id"
      class="flex items-center gap-2 px-3 py-1.5 rounded-full text-sm cursor-pointer transition-colors"
      :class="selectedIds().includes(doc.id)
        ? 'bg-[var(--color-primary)] text-white'
        : 'bg-[var(--surface-card)] border border-[var(--border-default)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]'"
    >
      <input
        type="checkbox"
        :value="doc.id"
        :checked="selectedIds().includes(doc.id)"
        class="hidden"
        @change="toggleMultiple(doc.id)"
      />
      {{ doc.filename }}
    </label>
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
      class="p-3 border rounded-xl cursor-pointer transition-all"
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
        class="flex items-center gap-3 p-3 rounded-xl border border-[var(--border-default)] cursor-pointer hover:border-[var(--color-primary)] transition-colors"
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
