<template>
  <div class="flex items-center justify-between mb-8">
    <div>
      <h1 class="text-2xl font-semibold text-[var(--text-primary)]">{{ title }}</h1>
      <p v-if="subtitle" class="text-sm text-[var(--text-muted)] mt-1">{{ subtitle }}</p>
    </div>
    <slot name="actions" />
  </div>
</template>

<script setup lang="ts">
/**
 * PageHeader（P2-2）：统一页面标题块（h1 + 副标题 + 右侧动作区）。
 *
 * 替代 10 个视图手写的标题块。入场动画由各视图的 gsap.context 按
 * 结构选择器（h1 / h1 + p）驱动，故不暴露内部 ref。
 */
defineProps<{
  title: string
  subtitle?: string
}>()
</script>
