<template>
  <div class="card overflow-hidden">
    <!-- Header: title + actions -->
    <div class="flex items-start justify-between gap-3 px-5 pt-5 pb-3 border-b border-[var(--border-default)]">
      <div class="min-w-0 flex-1">
        <h2 class="text-lg font-semibold text-[var(--text-primary)]">
          {{ note.title || '未命名笔记' }}
        </h2>
        <div class="flex items-center gap-2 flex-wrap mt-2">
          <span
            v-for="tag in normalizedTags"
            :key="tag"
            class="text-xs px-2 py-0.5 bg-[var(--bg-tertiary)] text-[var(--text-secondary)] rounded-full"
          >{{ tag }}</span>
          <span v-if="courseName" class="text-xs text-[var(--color-accent)] bg-[var(--color-accent-light)] px-2 py-0.5 rounded-full">
            {{ courseName }}
          </span>
          <span class="text-xs text-[var(--text-muted)]">{{ formatDate(note.updated_at || note.created_at) }}</span>
        </div>
      </div>
      <div class="flex items-center gap-2 shrink-0">
        <el-button type="primary" plain @click="$emit('edit')">
          <el-icon class="mr-1"><Edit /></el-icon>
          编辑
        </el-button>
        <el-button @click="$emit('close')" text>
          <el-icon class="mr-1"><Close /></el-icon>
          返回
        </el-button>
      </div>
    </div>

    <!-- Rendered markdown body -->
    <div class="px-5 py-5">
      <div
        v-if="html"
        class="note-md prose prose-sm max-w-none text-[var(--text-primary)]"
        v-html="html"
      />
      <EmptyState
        v-else
        size="sm"
        :icon="EditPen"
        message="这篇笔记还没有正文"
      >
        <el-button type="primary" plain @click="$emit('edit')">去编辑</el-button>
      </EmptyState>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Edit, Close, EditPen } from '@/components/icons'
import EmptyState from './common/EmptyState.vue'
import { useMarkdown } from '../composables/useMarkdown'
import { formatRelativeTime } from '../composables/useFormat'
import type { NoteDetail } from '../stores/note'

const props = defineProps<{
  note: NoteDetail
  courseName?: string
}>()

defineEmits<{
  edit: []
  close: []
}>()

const { renderMarkdown } = useMarkdown()
const formatDate = formatRelativeTime

const normalizedTags = computed<string[]>(() =>
  (props.note.tags || [])
    .map(t => (typeof t === 'string' ? t : t?.name))
    .filter(Boolean) as string[]
)

const html = computed(() => renderMarkdown(props.note.content || ''))
</script>

<style scoped>
.note-md :deep(h1) {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0.25rem 0 0.75rem;
}
.note-md :deep(h2) {
  font-size: 1.2rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 1.25rem 0 0.5rem;
}
.note-md :deep(h3),
.note-md :deep(h4) {
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 1rem 0 0.4rem;
}
.note-md :deep(p) {
  margin: 0.55rem 0;
  line-height: 1.75;
  color: var(--text-secondary);
}
.note-md :deep(ul),
.note-md :deep(ol) {
  margin: 0.5rem 0;
  padding-left: 1.25rem;
}
.note-md :deep(ul) {
  list-style: disc;
}
.note-md :deep(ol) {
  list-style: decimal;
}
.note-md :deep(li) {
  margin: 0.25rem 0;
  line-height: 1.65;
  color: var(--text-secondary);
}
.note-md :deep(strong) {
  color: var(--text-primary);
  font-weight: 600;
}
.note-md :deep(blockquote) {
  margin: 0.75rem 0;
  padding: 0.25rem 0 0.25rem 1rem;
  border-left: 3px solid var(--border-default);
  color: var(--text-muted);
}
.note-md :deep(pre.hljs),
.note-md :deep(pre) {
  margin: 0.75rem 0;
  padding: 0.85rem 1rem;
  border-radius: 8px;
  background: var(--bg-tertiary);
  overflow-x: auto;
  font-size: 0.85rem;
  line-height: 1.55;
}
.note-md :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.875em;
}
.note-md :deep(p code),
.note-md :deep(li code) {
  background: var(--bg-tertiary);
  padding: 0.1em 0.35em;
  border-radius: 4px;
  color: var(--text-primary);
}
.note-md :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 0.75rem 0;
  font-size: 0.9rem;
}
.note-md :deep(th),
.note-md :deep(td) {
  border: 1px solid var(--border-default);
  padding: 0.45rem 0.65rem;
  text-align: left;
}
.note-md :deep(th) {
  background: var(--bg-secondary);
  font-weight: 600;
  color: var(--text-primary);
}
.note-md :deep(hr) {
  border: none;
  border-top: 1px solid var(--border-default);
  margin: 1.25rem 0;
}
.note-md :deep(a) {
  color: var(--color-primary);
  text-decoration: underline;
}
</style>
