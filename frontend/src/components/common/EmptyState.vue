<template>
  <div class="text-center" :class="sizeClass">
    <!-- 精修（批次3）：加边框与 secondary 图标色，空状态提气但不喧宾夺主 -->
    <div
      class="mx-auto mb-4 bg-[var(--bg-tertiary)] border border-[var(--border-default)] rounded-full flex items-center justify-center"
      :class="iconWrapClass"
    >
      <el-icon v-if="icon" :class="iconClass"><component :is="icon" /></el-icon>
      <svg v-else-if="svgPath" class="text-[var(--text-secondary)]" :class="svgClass" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="svgPath" />
      </svg>
    </div>
    <p class="text-[var(--text-secondary)] mb-1">{{ message }}</p>
    <p v-if="hint" class="text-sm text-[var(--text-muted)] mb-4">{{ hint }}</p>
    <div v-else class="mb-4"></div>
    <slot />
  </div>
</template>

<script setup lang="ts">
/**
 * EmptyState（P2-2）：统一空状态展示。
 *
 * 替代 8 个视图中 5 种手写变体（圆形图标 + 文案 + CTA）。
 * icon 传 Element Plus 图标组件；无 EP 图标时可用 svgPath 传路径。
 */
import { computed } from 'vue'
import type { Component } from 'vue'

const props = withDefaults(defineProps<{
  /** Element Plus 图标组件（如 Tickets） */
  icon?: Component
  /** 手写 SVG path（无 EP 图标时用） */
  svgPath?: string
  message: string
  /** 次级提示文案（可选；主文案下方的浅色说明行） */
  hint?: string
  size?: 'sm' | 'md' | 'lg'
}>(), {
  size: 'md'
})

const sizeClass = computed(() => ({
  sm: 'py-8',
  md: 'py-12',
  lg: 'py-16'
}[props.size]))

const iconWrapClass = computed(() => ({
  sm: 'w-12 h-12',
  md: 'w-16 h-16',
  lg: 'w-20 h-20'
}[props.size]))

const iconClass = computed(() => ({
  sm: 'w-6 h-6 text-[var(--text-secondary)]',
  md: 'w-8 h-8 text-[var(--text-secondary)]',
  lg: 'w-10 h-10 text-[var(--text-secondary)]'
}[props.size]))

const svgClass = computed(() => ({
  sm: 'w-6 h-6',
  md: 'w-8 h-8',
  lg: 'w-10 h-10'
}[props.size]))
</script>
