<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  TIER_LABEL,
  type AchievementDef
} from './achievementCatalog'

const props = defineProps<{
  modelValue: boolean
  /** 仅已解锁成就——未解锁不进入下拉 */
  achievements: AchievementDef[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'select', id: string): void
}>()

const rootRef = ref<HTMLElement | null>(null)
/** 拖拽后抑制 click 误触发上墙 */
const suppressClick = ref(false)

const open = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v)
})

function onItemDragStart(e: DragEvent, id: string): void {
  if (!e.dataTransfer) return
  suppressClick.value = true
  e.dataTransfer.effectAllowed = 'copy'
  e.dataTransfer.setData('text/achievement-id', id)
  e.dataTransfer.setData('text/plain', id)
}

function onItemDragEnd(): void {
  // 延迟清标志，避免 dragend 后同刻 click
  window.setTimeout(() => {
    suppressClick.value = false
  }, 80)
}

function onItemClick(id: string): void {
  if (suppressClick.value) return
  emit('select', id)
}

function onDocClick(e: MouseEvent): void {
  const root = rootRef.value
  if (!root) return
  if (!root.contains(e.target as Node)) open.value = false
}

function onKeydown(e: KeyboardEvent): void {
  if (e.key === 'Escape') open.value = false
}

onMounted(() => {
  document.addEventListener('mousedown', onDocClick, true)
  document.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onDocClick, true)
  document.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div ref="rootRef" class="relative inline-block" data-test="achievement-wall-root">
    <slot name="trigger" :toggle="() => (open = !open)" :open="open" />

    <Transition name="wall-drop">
      <div
        v-if="open"
        class="wall-dropdown absolute right-0 top-full mt-2 z-50 w-[min(360px,calc(100vw-2rem))] rounded-2xl border border-[var(--border-default)] bg-[var(--surface-card)] shadow-xl overflow-hidden wall-panel"
        data-test="achievement-wall-dropdown"
        role="menu"
      >
        <div class="px-4 pt-3 pb-2">
          <div class="text-sm font-semibold text-[var(--text-primary)]">成就墙</div>
          <div class="text-[11px] text-[var(--text-muted)] mt-0.5">
            已解锁 {{ achievements.length }} 枚 · 点选贴上上方画布
          </div>
        </div>

        <!-- 顶部操作提示 + 虚线分割（对齐参考稿） -->
        <div class="px-4 pb-3">
          <div class="drag-hint text-xs text-[var(--text-muted)] text-center py-2">
            将贴纸拖拽到上方区域
          </div>
          <div class="dash-divider" aria-hidden="true" />
        </div>

        <div class="max-h-[min(380px,58vh)] overflow-y-auto px-3 pb-3">
          <div
            v-if="!achievements.length"
            class="px-2 py-12 text-center"
            data-test="achievement-wall-empty"
          >
            <div class="mx-auto w-12 h-12 rounded-2xl bg-[var(--bg-secondary)] flex items-center justify-center text-lg opacity-60">
              ★
            </div>
            <p class="mt-3 text-xs text-[var(--text-muted)]">还没有解锁成就，继续学习吧</p>
          </div>

          <!-- 贴纸宫格：可拖到上方画布，也可点击上墙 -->
          <div
            v-else
            class="sticker-grid"
            data-test="achievement-sticker-grid"
          >
            <button
              v-for="item in achievements"
              :key="item.id"
              type="button"
              class="sticker-cell"
              :data-test="`wall-item-${item.id}`"
              :title="`${item.name} · 拖到上方区域或点击上墙`"
              draggable="true"
              @dragstart="onItemDragStart($event, item.id)"
              @dragend="onItemDragEnd"
              @click="onItemClick(item.id)"
            >
              <div class="sticker-frame">
                <img
                  :src="item.image"
                  :alt="item.name"
                  class="sticker-img"
                  draggable="false"
                />
              </div>
              <div class="sticker-name">{{ item.name }}</div>
              <span class="tier-chip" :class="`tier-${item.tier}`">
                {{ TIER_LABEL[item.tier] }}
              </span>
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.drag-hint {
  letter-spacing: 0.02em;
  color: var(--text-muted);
}

.dash-divider {
  height: 0;
  border-top: 1px dashed var(--border-hover, var(--border-default));
  opacity: 0.95;
}

.sticker-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px 8px;
}

.sticker-cell {
  appearance: none;
  border: none;
  background: transparent;
  cursor: grab;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 8px 4px 10px;
  border-radius: 14px;
  transition: background 0.15s ease, transform 0.15s ease;
}

.sticker-cell:active {
  cursor: grabbing;
}

.sticker-cell:hover {
  background: var(--bg-hover);
  transform: translateY(-1px);
}

.sticker-cell:active {
  transform: translateY(0);
}

/* 浅底/暗底点阵画板，突出贴纸独立感 */
.sticker-frame {
  width: 72px;
  height: 72px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 18px;
  background-color: var(--bg-secondary);
  background-image: radial-gradient(
    circle,
    var(--sticker-dot, rgba(15, 23, 42, 0.08)) 1px,
    transparent 1.1px
  );
  background-size: 10px 10px;
  border: 1px solid var(--border-default);
}

.sticker-img {
  width: 60px;
  height: 60px;
  object-fit: contain;
  filter: drop-shadow(var(--sticker-shadow, 0 3px 6px rgba(15, 23, 42, 0.12)));
  pointer-events: none;
}

.sticker-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
  text-align: center;
  line-height: 1.25;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tier-chip {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 999px;
  font-weight: 500;
  border: 1px solid transparent;
  line-height: 1.4;
}

.tier-common {
  background: var(--color-primary-light);
  color: var(--text-secondary);
  border-color: var(--border-default);
}

.tier-rare {
  background: rgba(59, 130, 246, 0.12);
  color: #2563eb;
  border-color: rgba(59, 130, 246, 0.25);
}

.tier-epic {
  background: rgba(139, 92, 246, 0.14);
  color: #7c3aed;
  border-color: rgba(139, 92, 246, 0.28);
}

.wall-drop-enter-active,
.wall-drop-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.wall-drop-enter-from,
.wall-drop-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

/* ── 暗色适配（html.dark / .dark 双保险） ── */
html.dark .sticker-frame,
:global(.dark) .sticker-frame {
  --sticker-dot: rgba(255, 255, 255, 0.12);
  background-color: var(--bg-tertiary);
  border-color: var(--border-default);
}

html.dark .sticker-img,
:global(.dark) .sticker-img {
  --sticker-shadow: 0 3px 8px rgba(0, 0, 0, 0.35);
}

html.dark .tier-rare,
:global(.dark) .tier-rare {
  background: rgba(59, 130, 246, 0.18);
  color: #93c5fd;
  border-color: rgba(59, 130, 246, 0.35);
}

html.dark .tier-epic,
:global(.dark) .tier-epic {
  background: rgba(139, 92, 246, 0.2);
  color: #c4b5fd;
  border-color: rgba(139, 92, 246, 0.4);
}

html.dark .sticker-cell:hover,
:global(.dark) .sticker-cell:hover {
  background: rgba(255, 255, 255, 0.06);
}

html.dark .wall-panel,
:global(.dark) .wall-panel {
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.45);
}
</style>
