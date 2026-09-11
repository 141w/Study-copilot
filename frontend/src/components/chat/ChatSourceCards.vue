<template>
  <div v-if="sources && sources.length > 0" class="mt-3 grid grid-cols-1 gap-2">
    <div
      v-for="(source, sidx) in sources"
      :key="sidx"
      :id="`source-card-${source.index}`"
      class="source-card bg-[var(--surface-card)] rounded-xl border border-[var(--border-default)] text-sm transition-colors duration-200 hover:border-[var(--border-hover)] overflow-hidden"
    >
      <!-- 标题行：默认只展示这一行，点击展开正文摘要 -->
      <button
        type="button"
        class="w-full flex items-center gap-2 p-3 text-left hover:bg-[var(--bg-hover)] transition-colors"
        :aria-expanded="isExpanded(source.index)"
        :data-test="`source-card-toggle-${source.index}`"
        @click="toggle(source.index)"
      >
        <span
          class="w-5 h-5 rounded-full bg-[var(--color-primary)] text-[var(--text-inverse)] text-[11px] flex items-center justify-center font-semibold shrink-0"
        >
          {{ source.index }}
        </span>
        <span v-if="source.source" class="font-medium text-[var(--text-primary)] truncate min-w-0 flex-1">
          {{ source.source }}
        </span>
        <span v-if="source.page" class="text-xs text-[var(--text-muted)] shrink-0">P{{ source.page }}</span>
        <span
          class="text-[10px] px-1.5 py-0.5 rounded border border-[var(--border-default)] text-[var(--text-muted)] group-hover:text-[var(--text-secondary)] shrink-0"
          data-test="source-card-expand-hint"
        >
          {{ isExpanded(source.index) ? '收起' : '详情' }}
        </span>
      </button>

      <!-- 正文摘要：默认折叠 -->
      <div
        v-if="isExpanded(source.index)"
        class="px-3.5 pb-3 pt-0"
        data-test="source-card-body"
      >
        <div v-if="source.text" class="text-xs text-[var(--text-secondary)] leading-relaxed pl-7">
          {{ source.text }}
        </div>
        <div v-else class="text-xs text-[var(--text-muted)] pl-7 italic">（无正文摘要）</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import type { Source } from '@/types/models'

const props = defineProps<{
  sources?: Source[]
}>()

/** 已展开的来源 index 集合；默认全部只显示标题 */
const expandedSet = ref<Set<number>>(new Set())

function isExpanded(index: number | undefined): boolean {
  if (index == null) return false
  return expandedSet.value.has(index)
}

function toggle(index: number | undefined): void {
  if (index == null) return
  const next = new Set(expandedSet.value)
  if (next.has(index)) next.delete(index)
  else next.add(index)
  expandedSet.value = next
}

// 来源列表整体更换时重置折叠态，避免残留旧 index
watch(
  () => props.sources,
  () => {
    expandedSet.value = new Set()
  }
)
</script>
