<template>
  <!--
    P1-2（design-taste-frontend §4.5）：骨架屏加载态，匹配最终布局形状。
    - variant="rows"   ：行式列表（文档列表等）
    - variant="cards"  ：三列卡片网格（笔记网格等）
    - variant="blocks" ：分组块（做题历史：圆点+两行文本）
    - variant="text"   ：阅读区段落（文档阅读器等）
    shimmer 动画在 prefers-reduced-motion 下自动停用（CSS 兜底）。
  -->
  <div aria-busy="true" aria-label="加载中" role="status">
    <!-- 阅读段落骨架（批次6）：宽窄交替的文本行近似一页文档 -->
    <div v-if="variant === 'text'" class="space-y-3" data-testid="skeleton-text">
      <div v-for="(w, i) in lineWidths.slice(0, count)" :key="i" class="skeleton h-4 rounded" :style="{ width: w }"></div>
    </div>

    <!-- 行式骨架 -->
    <div v-if="variant === 'rows'" class="divide-y divide-[var(--border-default)]" data-testid="skeleton-rows">
      <div v-for="i in count" :key="i" class="p-4 flex items-center gap-4">
        <div class="skeleton w-10 h-10 rounded-lg flex-shrink-0"></div>
        <div class="flex-1 space-y-2">
          <div class="skeleton h-4 rounded w-2/5"></div>
          <div class="skeleton h-3 rounded w-1/4"></div>
        </div>
        <div class="skeleton w-5 h-5 rounded flex-shrink-0"></div>
      </div>
    </div>

    <!-- 卡片网格骨架 -->
    <div v-else-if="variant === 'cards'" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="skeleton-cards">
      <div v-for="i in count" :key="i" class="card p-4">
        <div class="flex items-center gap-2 mb-3">
          <div class="skeleton w-5 h-5 rounded"></div>
          <div class="skeleton h-3 rounded w-1/3"></div>
        </div>
        <div class="space-y-2">
          <div class="skeleton h-4 rounded w-full"></div>
          <div class="skeleton h-3 rounded w-4/5"></div>
          <div class="skeleton h-3 rounded w-3/5"></div>
        </div>
        <div class="flex gap-1.5 mt-3">
          <div class="skeleton h-4 w-10 rounded-full"></div>
          <div class="skeleton h-4 w-12 rounded-full"></div>
        </div>
      </div>
    </div>

    <!-- 分组块骨架（做题历史） -->
    <div v-else class="space-y-4" data-testid="skeleton-blocks">
      <div v-for="i in count" :key="i" class="card p-4">
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-3">
            <div class="skeleton h-4 rounded w-20"></div>
            <div class="skeleton h-3 rounded w-12"></div>
          </div>
          <div class="skeleton h-4 w-14 rounded"></div>
        </div>
        <div class="space-y-2">
          <div class="flex items-start gap-3 p-3 bg-[var(--bg-secondary)] rounded-lg">
            <div class="skeleton w-6 h-6 rounded-full flex-shrink-0"></div>
            <div class="flex-1 space-y-2">
              <div class="skeleton h-3.5 rounded w-full"></div>
              <div class="skeleton h-3 rounded w-2/3"></div>
            </div>
          </div>
          <div class="flex items-start gap-3 p-3 bg-[var(--bg-secondary)] rounded-lg">
            <div class="skeleton w-6 h-6 rounded-full flex-shrink-0"></div>
            <div class="flex-1 space-y-2">
              <div class="skeleton h-3.5 rounded w-5/6"></div>
              <div class="skeleton h-3 rounded w-1/2"></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

withDefaults(
  defineProps<{
    /** 骨架项数量（匹配典型数据条数） */
    count?: number
    /** 形状变体：行式 / 卡片网格 / 分组块 / 阅读段落 */
    variant?: 'rows' | 'cards' | 'blocks' | 'text'
  }>(),
  { count: 3, variant: 'rows' }
)

/** text 变体：循环宽窄节奏（末行收短模拟段落结尾） */
const lineWidths = computed(() => {
  const cycle = ['100%', '92%', '100%', '85%', '100%', '96%', '70%']
  return Array.from({ length: 12 }, (_, i) => cycle[i % cycle.length])
})
</script>

<style scoped>
/* 骨架底色 + shimmer 扫光；色值全走 token，双主题自动适配 */
.skeleton {
  background-color: var(--bg-tertiary);
  position: relative;
  overflow: hidden;
}

.skeleton::after {
  content: '';
  position: absolute;
  inset: 0;
  transform: translateX(-100%);
  background: linear-gradient(
    90deg,
    transparent,
    color-mix(in srgb, var(--text-primary) 4%, transparent),
    transparent
  );
  animation: skeleton-shimmer 1.5s infinite;
}

@keyframes skeleton-shimmer {
  100% {
    transform: translateX(100%);
  }
}

/* P1-1（§6.B）：减少动态偏好下停用 shimmer，仅保留静态底色 */
@media (prefers-reduced-motion: reduce) {
  .skeleton::after {
    animation: none;
  }
}
</style>
