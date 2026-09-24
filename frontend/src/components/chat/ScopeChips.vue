<template>
  <div class="w-full" data-test="scope-chips">
    <div v-if="chips.length" class="flex flex-wrap gap-1.5 mb-1.5">
      <span
        v-for="chip in chips"
        :key="chip.key"
        class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] bg-[var(--color-primary-light)] text-[var(--text-primary)] border border-[var(--border-default)]"
        :data-test="`scope-chip-${chip.kind}`"
      >
        <span class="opacity-60">{{ chip.kind === 'course' ? '课' : '文' }}</span>
        <span class="max-w-[140px] truncate">{{ chip.label }}</span>
        <button
          type="button"
          class="opacity-60 hover:opacity-100"
          :aria-label="`移除 ${chip.label}`"
          @click.stop="removeChip(chip)"
        >×</button>
      </span>
    </div>

    <!-- @ 候选弹层 -->
    <div
      v-if="mentionOpen && filteredCandidates.length"
      class="absolute z-50 mt-1 w-72 max-h-56 overflow-y-auto rounded-xl border border-[var(--border-default)] bg-[var(--surface-card)] shadow-md"
      data-test="mention-popup"
    >
      <div
        v-for="(item, i) in filteredCandidates"
        :key="item.key"
        class="px-3 py-2 text-sm cursor-pointer flex items-center gap-2"
        :class="i === mentionIndex ? 'bg-[var(--bg-hover)]' : ''"
        data-test="mention-item"
        @mousedown.prevent="pickMention(item)"
      >
        <span class="text-[10px] px-1.5 rounded bg-[var(--bg-secondary)] text-[var(--text-muted)]">
          {{ item.kind === 'course' ? '课程' : item.kind === 'knowledge' ? '知识库' : '文档' }}
        </span>
        <span class="truncate text-[var(--text-primary)]">{{ item.label }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

export type ScopeChip = {
  key: string
  kind: 'doc' | 'course' | 'knowledge'
  id: string
  label: string
}

const props = withDefaults(
  defineProps<{
    chips?: ScopeChip[]
    candidates?: ScopeChip[]
    mentionOpen?: boolean
  }>(),
  { chips: () => [], candidates: () => [], mentionOpen: false }
)

const emit = defineEmits<{
  (e: 'remove', chip: ScopeChip): void
  (e: 'pick', chip: ScopeChip): void
  (e: 'update:mentionOpen', v: boolean): void
}>()

const mentionIndex = ref(0)
const query = ref('')

const filteredCandidates = computed(() => {
  const q = query.value.toLowerCase()
  const list = props.candidates.filter(c => !props.chips.some(x => x.key === c.key))
  if (!q) return list.slice(0, 8)
  return list.filter(c => c.label.toLowerCase().includes(q)).slice(0, 8)
})

watch(filteredCandidates, () => {
  if (mentionIndex.value >= filteredCandidates.value.length) mentionIndex.value = 0
})

function removeChip(chip: ScopeChip): void {
  emit('remove', chip)
}

function pickMention(item: ScopeChip): void {
  emit('pick', item)
  emit('update:mentionOpen', false)
  query.value = ''
  mentionIndex.value = 0
}

function setQuery(q: string): void {
  query.value = q
}

function move(delta: number): boolean {
  const n = filteredCandidates.value.length
  if (!n || !props.mentionOpen) return false
  mentionIndex.value = (mentionIndex.value + delta + n) % n
  return true
}

function pickActive(): boolean {
  if (!props.mentionOpen) return false
  const item = filteredCandidates.value[mentionIndex.value]
  if (!item) return false
  pickMention(item)
  return true
}

defineExpose({ setQuery, move, pickActive, filteredCandidates })
</script>
