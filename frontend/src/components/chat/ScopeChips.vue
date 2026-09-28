<template>
  <div class="scope-chips-wrapper w-full" data-test="scope-chips">
    <!-- 胶囊展示区 (复刻 WeKnora selected-tags-inline & mention-chip 规范) -->
    <div v-if="chips.length" class="selected-tags-inline flex flex-wrap items-center gap-1.5 py-1.5 px-3">
      <span
        v-for="chip in chips"
        :key="chip.key"
        class="mention-chip"
        :class="`mention-chip--${chip.kind}`"
        :data-test="`scope-chip-${chip.kind}`"
      >
        <span class="mention-chip__icon">
          <!-- 课程图标 -->
          <svg v-if="chip.kind === 'course'" class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 14l9-5-9-5-9 5 9 5z" />
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 14l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0012 20.055a11.952 11.952 0 00-6.824-2.998 12.078 12.078 0 01.665-6.479L12 14z" />
          </svg>
          <!-- 知识库图标 -->
          <svg v-else-if="chip.kind === 'knowledge'" class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
          </svg>
          <!-- 文档图标 -->
          <svg v-else class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        </span>
        <span class="mention-chip__name" :title="chip.label">{{ chip.label }}</span>
        <span
          class="mention-chip__remove"
          :aria-label="`移除 ${chip.label}`"
          @click.stop="removeChip(chip)"
        >×</span>
      </span>
    </div>

    <!-- @ 候选弹层 (参照 WeKnora MentionSelector 浮层规范) -->
    <div
      v-if="mentionOpen"
      class="mention-selector-popup absolute bottom-full left-0 mb-2 w-80 max-h-64 overflow-y-auto rounded-xl border border-[var(--border-default)] bg-[var(--bg-primary)] shadow-xl z-50 p-1.5 animate-in fade-in zoom-in-95 duration-150"
      data-test="mention-popup"
    >
      <div class="px-2.5 py-1.5 text-[11px] font-medium text-[var(--text-muted)] border-b border-[var(--border-subtle)] flex items-center justify-between">
        <span>引用范围 (支持课程 / 文档)</span>
        <span class="text-[10px] opacity-70">↑↓ 切换 · Enter 选中</span>
      </div>
      <div v-if="filteredCandidates.length" class="py-1 space-y-0.5">
        <div
          v-for="(item, i) in filteredCandidates"
          :key="item.key"
          class="mention-item px-2.5 py-2 rounded-lg text-xs cursor-pointer flex items-center justify-between transition-colors outline-none"
          :class="i === mentionIndex ? 'bg-[var(--bg-hover)] text-[var(--text-primary)]' : 'text-[var(--text-secondary)]'"
          data-test="mention-item"
          role="button"
          tabindex="0"
          @mouseenter="mentionIndex = i"
          @mousedown.prevent="pickMention(item)"
          @click="pickMention(item)"
          @keydown.enter.prevent="pickMention(item)"
        >
          <div class="flex items-center gap-2 min-w-0 flex-1">
            <span
              class="w-5 h-5 rounded flex items-center justify-center shrink-0 text-xs"
              :class="item.kind === 'course' ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300' : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300'"
            >
              <svg v-if="item.kind === 'course'" class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 14l9-5-9-5-9 5 9 5z" />
              </svg>
              <svg v-else class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </span>
            <span class="truncate font-medium">{{ item.label }}</span>
          </div>
          <span class="text-[10px] px-1.5 py-0.5 rounded font-mono shrink-0 ml-2" :class="item.kind === 'course' ? 'text-purple-600 bg-purple-50 dark:bg-purple-950/50' : 'text-emerald-600 bg-emerald-50 dark:bg-emerald-950/50'">
            {{ item.kind === 'course' ? '课程' : '文档' }}
          </span>
        </div>
      </div>
      <div v-else class="py-4 text-center text-xs text-[var(--text-muted)]">
        <span v-if="candidates.length === 0">暂无可用课程或文档</span>
        <span v-else-if="query">未找到匹配项</span>
        <span v-else>所有文档已在引用范围中</span>
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
  if (!q) return list.slice(0, 10)
  return list.filter(c => c.label.toLowerCase().includes(q)).slice(0, 10)
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

function selectCurrent(): boolean {
  if (!props.mentionOpen) return false
  const cur = filteredCandidates.value[mentionIndex.value]
  if (cur) {
    pickMention(cur)
    return true
  }
  return false
}

defineExpose({ setQuery, move, selectCurrent })
</script>

<style scoped>
/* 参照 WeKnora chat-resource-chips.less 与 mention-chip 规范 */
.selected-tags-inline {
  border-bottom: 1px solid var(--border-subtle, rgba(0, 0, 0, 0.05));
  background: var(--bg-primary, #ffffff);
  border-top-left-radius: 15px;
  border-top-right-radius: 15px;
}

.dark .selected-tags-inline {
  border-bottom-color: rgba(255, 255, 255, 0.06);
  background: #18181b;
}

.mention-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 26px;
  padding: 0 8px 0 6px;
  border-radius: 6px;
  font-size: 11.5px;
  font-weight: 500;
  line-height: 1;
  border: 1px solid var(--border-default, #e5e7eb);
  background: var(--bg-secondary, #f9fafb);
  color: var(--text-primary, #1f2937);
  box-sizing: border-box;
  transition: all 0.15s ease;
  user-select: none;
}

.mention-chip:hover {
  background: var(--bg-hover, #f3f4f6);
  border-color: var(--border-hover, #d1d5db);
}

.dark .mention-chip {
  background: #27272a;
  border-color: #3f3f46;
  color: #f3f4f6;
}

.dark .mention-chip:hover {
  background: #323238;
}

.mention-chip__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--color-primary, #10b981);
}

.mention-chip--course .mention-chip__icon {
  color: #8b5cf6;
}

.mention-chip__name {
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mention-chip__remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  margin-left: 2px;
  border-radius: 50%;
  font-size: 13px;
  line-height: 1;
  cursor: pointer;
  opacity: 0.55;
  transition: all 0.12s ease;
}

.mention-chip__remove:hover {
  opacity: 1;
  background: rgba(0, 0, 0, 0.08);
  color: #ef4444;
}

.dark .mention-chip__remove:hover {
  background: rgba(255, 255, 255, 0.15);
  color: #f87171;
}
</style>
