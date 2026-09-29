<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  ACHIEVEMENT_LAYOUT_KEY,
  type StickerDef,
  type StickerLayoutItem
} from './achievementStickers'

const STICKER_PX = 64

const props = withDefaults(
  defineProps<{
    stickers?: StickerDef[]
    /** 是否允许拖拽调整落点 */
    draggable?: boolean
    /** 是否作为成就墙拖放目标 */
    dropTarget?: boolean
  }>(),
  {
    draggable: true,
    dropTarget: true
  }
)

const emit = defineEmits<{
  (e: 'layout-change', layout: Record<string, StickerLayoutItem>): void
  /** 点击（非拖拽）贴纸时移除 */
  (e: 'remove', id: string): void
  /** 从成就墙拖放到画布（坐标为舞台百分比） */
  (e: 'drop', payload: { id: string; x: number; y: number }): void
}>()

const stageRef = ref<HTMLElement | null>(null)
const layout = ref<Record<string, StickerLayoutItem>>({})
const draggingId = ref<string | null>(null)
const dragMoved = ref(false)

const stickers = computed(() => props.stickers ?? [])

function loadLayout(): void {
  if (typeof window === 'undefined') return
  try {
    const raw = localStorage.getItem(ACHIEVEMENT_LAYOUT_KEY)
    if (raw) layout.value = JSON.parse(raw)
  } catch {
    layout.value = {}
  }
}

function saveLayout(): void {
  try {
    localStorage.setItem(ACHIEVEMENT_LAYOUT_KEY, JSON.stringify(layout.value))
  } catch {
    /* 忽略配额/隐私模式失败 */
  }
  emit('layout-change', { ...layout.value })
}

function stickerPos(def: StickerDef): StickerLayoutItem {
  return layout.value[def.id] ?? { x: def.x, y: def.y, rot: def.rot }
}

function stickerStyle(def: StickerDef) {
  const pos = stickerPos(def)
  return {
    left: `${pos.x}%`,
    top: `${pos.y}%`,
    transform: `translate(-50%, -50%) rotate(${pos.rot}deg)`,
    width: `${STICKER_PX}px`,
    height: `${STICKER_PX}px`,
    zIndex: draggingId.value === def.id ? 20 : 10,
    touchAction: props.draggable ? 'none' : undefined
  }
}

function onPointerDown(e: PointerEvent, id: string): void {
  if (!props.draggable) return
  const el = e.currentTarget as HTMLElement | null
  if (!el) return
  // 阻断浏览器默认拖影（图片 ghost 阴影）
  e.preventDefault()
  el.setPointerCapture(e.pointerId)
  draggingId.value = id
  dragMoved.value = false
}

function onPointerMove(e: PointerEvent): void {
  if (!draggingId.value || !stageRef.value) return
  const stage = stageRef.value.getBoundingClientRect()
  if (stage.width <= 0 || stage.height <= 0) return
  dragMoved.value = true
  const x = ((e.clientX - stage.left) / stage.width) * 100
  const y = ((e.clientY - stage.top) / stage.height) * 100
  const prev = layout.value[draggingId.value]
  const defRot = stickers.value.find((s) => s.id === draggingId.value)?.rot ?? 0
  layout.value[draggingId.value] = {
    x: Math.min(98, Math.max(2, x)),
    y: Math.min(94, Math.max(6, y)),
    rot: prev?.rot ?? defRot
  }
}

function onPointerUp(e: PointerEvent): void {
  if (!draggingId.value) return
  const id = draggingId.value
  const el = e.currentTarget as HTMLElement | null
  try {
    el?.releasePointerCapture(e.pointerId)
  } catch {
    /* pointer capture 可能已释放 */
  }
  draggingId.value = null
  if (dragMoved.value) {
    saveLayout()
    dragMoved.value = false
    return
  }
  // 轻点（未拖动）→ 移除贴纸
  emit('remove', id)
}

function onDragOver(e: DragEvent): void {
  if (!props.dropTarget) return
  e.preventDefault()
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy'
}

function onDrop(e: DragEvent): void {
  if (!props.dropTarget) return
  e.preventDefault()
  const id =
    e.dataTransfer?.getData('text/achievement-id') ||
    e.dataTransfer?.getData('text/plain') ||
    ''
  if (!id || !stageRef.value) return
  const stage = stageRef.value.getBoundingClientRect()
  if (stage.width <= 0 || stage.height <= 0) return
  const x = Math.min(98, Math.max(2, ((e.clientX - stage.left) / stage.width) * 100))
  const y = Math.min(94, Math.max(6, ((e.clientY - stage.top) / stage.height) * 100))
  emit('drop', { id, x, y })
}

function resetLayout(): void {
  layout.value = {}
  saveLayout()
}

onMounted(() => {
  loadLayout()
})

defineExpose({ resetLayout })
</script>

<template>
  <div
    ref="stageRef"
    class="achievement-stage relative w-full min-h-[180px] sm:min-h-[220px]"
    data-test="achievement-stage"
    @dragover="onDragOver"
    @drop="onDrop"
  >
    <div
      v-for="def in stickers"
      :key="def.id"
      class="achievement-sticker absolute select-none"
      :class="[
        draggable ? 'cursor-grab active:cursor-grabbing' : 'cursor-default',
        draggingId === def.id ? 'is-dragging' : ''
      ]"
      :style="stickerStyle(def)"
      :data-test="`sticker-${def.id}`"
      :title="`${def.label} · 拖拽移动 / 点击移除`"
      role="button"
      :aria-label="def.label"
      @pointerdown="onPointerDown($event, def.id)"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerUp"
    >
      <div class="sticker-anim">
        <img
          class="sticker-img w-full h-full object-contain pointer-events-none"
          :src="def.img"
          :alt="def.label"
          draggable="false"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.achievement-stage {
  /* 仅作自由摆放容器，点阵背景由开放通栏 hero 承担 */
  background: transparent;
}

.achievement-sticker {
  will-change: left, top, transform;
  transition: filter 0.15s ease;
  /* 禁止系统拖影 / 选中残影 */
  -webkit-user-select: none;
  user-select: none;
  -webkit-user-drag: none;
  -webkit-touch-callout: none;
}

.achievement-sticker:hover:not(.is-dragging) {
  filter: brightness(1.04);
}

/* 拖拽中去掉 hover 提亮与阴影层，避免出现幽灵阴影 */
.achievement-sticker.is-dragging {
  filter: none !important;
  transition: none;
}

.achievement-sticker.is-dragging .sticker-img {
  filter: none !important;
  opacity: 0.96;
}

/* 落入画布动画（新贴纸挂载时播放一次） */
.sticker-anim {
  width: 100%;
  height: 100%;
  animation: sticker-drop-in 0.36s cubic-bezier(0.22, 1.2, 0.36, 1) both;
  -webkit-user-drag: none;
}

@keyframes sticker-drop-in {
  0% {
    opacity: 0;
    transform: translateY(-14px) scale(0.55);
  }
  60% {
    opacity: 1;
    transform: translateY(2px) scale(1.06);
  }
  100% {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@media (prefers-reduced-motion: reduce) {
  .sticker-anim {
    animation: none;
  }
}

.sticker-img {
  filter: drop-shadow(var(--sticker-shadow, 0 4px 8px rgba(15, 23, 42, 0.14)));
  -webkit-user-drag: none;
  user-select: none;
  pointer-events: none;
}

html.dark .sticker-img,
:global(.dark) .sticker-img {
  --sticker-shadow: 0 4px 10px rgba(0, 0, 0, 0.4);
}
</style>
