<template>
  <div
    ref="cardEl"
    class="card p-5 hover:shadow-md hover:outline hover:outline-2 hover:outline-[var(--color-primary)]/40 transition-all cursor-pointer group"
    tabindex="0"
    role="button"
    :aria-label="note.title ? `打开笔记: ${note.title}` : '打开未命名笔记'"
    @click="$emit('click', note)"
    @keydown.enter="$emit('click', note)"
    @keydown.space.prevent="$emit('click', note)"
  >
    <div class="flex items-start justify-between mb-2">
      <h3 class="font-semibold text-[var(--text-primary)] truncate flex-1 pr-2">{{ note.title || '未命名笔记' }}</h3>
      <div class="flex items-center gap-1 opacity-100 md:opacity-0 md:group-hover:opacity-100 md:focus-within:opacity-100 transition-opacity flex-shrink-0">
        <button
          @click.stop="$emit('edit', note)"
          aria-label="编辑笔记"
          class="p-1.5 text-[var(--text-muted)] hover:text-[var(--color-info)] hover:bg-[var(--color-info-light)] rounded transition-colors"
        >
          <el-icon class="w-4 h-4"><Edit /></el-icon>
        </button>
        <button
          @click.stop="$emit('delete', note)"
          aria-label="删除笔记"
          class="p-1.5 text-[var(--text-muted)] hover:text-[var(--color-error)] hover:bg-[var(--color-error-light)] rounded transition-colors"
        >
          <el-icon class="w-4 h-4"><Delete /></el-icon>
        </button>
      </div>
    </div>

    <p class="text-sm text-[var(--text-muted)] line-clamp-3 mb-3 leading-relaxed">{{ noteSummary }}</p>

    <div class="flex items-center gap-2 flex-wrap">
      <span v-for="tag in normalizedTags.slice(0, 3)" :key="tag"
        class="text-xs px-2 py-0.5 bg-[var(--bg-tertiary)] text-[var(--text-secondary)] rounded-full"
      >{{ tag }}</span>
      <span v-if="normalizedTags.length > 3" class="text-xs text-[var(--text-muted)]">
        +{{ normalizedTags.length - 3 }}
      </span>
    </div>

    <div class="flex items-center justify-between mt-3 pt-3 border-t border-[var(--border-default)]">
      <span class="text-xs text-[var(--text-muted)]">{{ formatDate(note.updated_at || note.created_at) }}</span>
      <span v-if="courseName" class="text-xs text-[var(--color-accent)] bg-[var(--color-accent-light)] px-2 py-0.5 rounded-full">
        {{ courseName }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Edit, Delete } from '@/components/icons'
import { useMarkdown } from '../composables/useMarkdown'
import { formatRelativeTime } from '../composables/useFormat'
import type { NoteDetail } from '../stores/note'

const props = defineProps<{
  /** NoteDetail 的 tags 兼容 string 与对象两种后端形态（渲染前归一化） */
  note: NoteDetail
  courseName?: string
}>()

defineEmits<{
  click: [note: NoteDetail]
  edit: [note: NoteDetail]
  delete: [note: NoteDetail]
}>()

const { stripMarkdown } = useMarkdown()

/** 归一化 tags 为字符串（后端列表/详情接口形态不同） */
const normalizedTags = computed<string[]>(() =>
  (props.note.tags || [])
    .map(t => (typeof t === 'string' ? t : t?.name))
    .filter(Boolean) as string[]
)

const noteSummary = computed(() => {
  if (!props.note.content) return ''
  const plain = stripMarkdown(props.note.content).replace(/\n+/g, ' ').trim()
  return plain.length > 200 ? plain.substring(0, 200) + '...' : plain
})

// P2-1：formatDate 由 useFormat.formatRelativeTime 替换（原为平行实现之一）
const formatDate = formatRelativeTime
</script>

<style scoped>
.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
