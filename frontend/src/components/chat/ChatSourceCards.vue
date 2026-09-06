<template>
  <div v-if="sources && sources.length > 0" class="mt-3 grid grid-cols-1 gap-2">
    <div
      v-for="(source, sidx) in sources"
      :key="sidx"
      :id="`source-card-${source.index}`"
      class="source-card p-3 bg-[var(--bg-secondary)] rounded-lg border border-[var(--border-default)] text-sm transition-all duration-300"
    >
      <div class="flex items-center gap-2 mb-1">
        <span
          class="w-4 h-4 rounded-full bg-[var(--color-primary)] text-[var(--text-inverse)] text-[10px] flex items-center justify-center font-medium"
        >
          {{ source.index }}
        </span>
        <span v-if="source.source" class="font-medium text-[var(--text-primary)]">{{ source.source }}</span>
        <span v-if="source.page" class="text-xs text-[var(--text-muted)]">P{{ source.page }}</span>
      </div>
      <div class="text-xs text-[var(--text-secondary)] line-clamp-2 leading-relaxed">{{ source.text }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Source } from '@/types/models'

defineProps<{
  sources?: Source[]
}>()
</script>
