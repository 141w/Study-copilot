<template>
  <div v-if="sources && sources.length > 0" class="mt-3 grid grid-cols-1 gap-2.5">
    <div
      v-for="(source, sidx) in sources"
      :key="sidx"
      :id="`source-card-${source.index}`"
      class="source-card p-3.5 bg-[var(--surface-card)] rounded-xl border border-[var(--border-default)] shadow-xs text-sm transition-all duration-300 hover:border-[var(--color-primary-light)] hover:shadow-sm"
    >
      <div class="flex items-center gap-2 mb-1.5">
        <span
          class="w-5 h-5 rounded-full bg-[var(--color-primary)] text-[var(--text-inverse)] text-[11px] flex items-center justify-center font-semibold shrink-0"
        >
          {{ source.index }}
        </span>
        <span v-if="source.source" class="font-medium text-[var(--text-primary)] truncate min-w-0">
          {{ source.source }}
        </span>
        <span v-if="source.page" class="text-xs text-[var(--text-muted)] shrink-0">P{{ source.page }}</span>
      </div>
      <div v-if="source.text" class="text-xs text-[var(--text-secondary)] line-clamp-3 leading-relaxed pl-7">
        {{ source.text }}
      </div>
      <div v-else class="text-xs text-[var(--text-muted)] pl-7 italic">（无正文摘要）</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Source } from '@/types/models'

defineProps<{
  sources?: Source[]
}>()
</script>
