<template>
  <div
    ref="cardEl"
    class="card p-5 hover:border-[var(--color-primary)] border-2 border-transparent transition-all cursor-pointer group"
    @click="$emit('click', note)"
  >
    <div class="flex items-start justify-between mb-2">
      <h3 class="font-semibold text-[var(--text-primary)] truncate flex-1 pr-2">{{ note.title || '未命名笔记' }}</h3>
      <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
        <button
          @click.stop="$emit('edit', note)"
          class="p-1.5 text-[var(--text-muted)] hover:text-[var(--color-info)] hover:bg-[var(--color-info-light)] rounded transition-colors"
          title="编辑笔记"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
          </svg>
        </button>
        <button
          @click.stop="$emit('delete', note)"
          class="p-1.5 text-[var(--text-muted)] hover:text-[var(--color-error)] hover:bg-[var(--color-error-light)] rounded transition-colors"
          title="删除笔记"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </button>
      </div>
    </div>

    <p class="text-sm text-[var(--text-muted)] line-clamp-3 mb-3 leading-relaxed">{{ noteSummary }}</p>

    <div class="flex items-center gap-2 flex-wrap">
      <span v-for="tag in (note.tags || []).slice(0, 3)" :key="tag"
        class="text-xs px-2 py-0.5 bg-[var(--bg-tertiary)] text-[var(--text-secondary)] rounded-full"
      >{{ tag }}</span>
      <span v-if="(note.tags || []).length > 3" class="text-xs text-[var(--text-muted)]">
        +{{ note.tags.length - 3 }}
      </span>
    </div>

    <div class="flex items-center justify-between mt-3 pt-3 border-t border-[var(--border-default)]">
      <span class="text-xs text-[var(--text-muted)]">{{ formatDate(note.updated_at || note.created_at) }}</span>
      <span v-if="courseName" class="text-xs text-[var(--color-accent)] bg-[var(--color-accent-light, #f3f0ff)] px-2 py-0.5 rounded-full">
        {{ courseName }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Note } from '../types/models'

const props = defineProps<{
  note: Note
  courseName?: string
}>()

defineEmits<{
  click: [note: Note]
  edit: [note: Note]
  delete: [note: Note]
}>()

const noteSummary = computed(() => {
  if (!props.note.content) return ''
  // Strip markdown formatting for preview
  const plain = props.note.content
    .replace(/#{1,6}\s+/g, '')
    .replace(/\*{1,2}([^*]+)\*{1,2}/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/\n+/g, ' ')
    .trim()
  return plain.length > 200 ? plain.substring(0, 200) + '...' : plain
})

function formatDate(dateStr: string): string {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return Math.floor(diff / 60000) + ' 分钟前'
  if (diff < 86400000) return Math.floor(diff / 3600000) + ' 小时前'
  if (diff < 172800000) return '昨天'
  if (diff < 604800000) return Math.floor(diff / 86400000) + ' 天前'
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}
</script>

<style scoped>
.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
