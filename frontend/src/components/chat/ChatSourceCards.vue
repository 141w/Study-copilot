<template>
  <div v-if="sources && sources.length > 0" class="space-y-1.5">
    <div
      v-for="(source, sidx) in sources"
      :key="sidx"
      :id="`source-card-${source.index}`"
      class="source-card"
      :class="{ 'source-card--open': isExpanded(source.index) }"
    >
      <!-- Header: single full-width button -->
      <button
        type="button"
        class="source-card__trigger"
        :aria-expanded="isExpanded(source.index)"
        :data-test="`source-card-toggle-${source.index}`"
        @click="toggle(source.index)"
      >
        <!-- Content area -->
        <span class="source-card__content">
          <span class="source-card__index">{{ source.index }}</span>
          <span
            v-if="source.source"
            class="source-card__name"
            :title="source.source"
          >{{ source.source }}</span>
          <span v-else class="source-card__name source-card__name--unknown">未知来源</span>
          <span v-if="source.page" class="source-card__page">P{{ source.page }}</span>
        </span>

        <!-- Right: state arrow（旋转指示展开态） -->
        <span class="source-card__cue">
          <el-icon class="source-card__arrow w-3 h-3">
            <ArrowRight />
          </el-icon>
        </span>
      </button>

      <!-- Expandable quote body -->
      <div
        v-if="isExpanded(source.index)"
        class="source-card__body"
        data-test="source-card-body"
      >
        <div class="source-card__body-main">
          <p v-if="source.text" class="source-card__quote">{{ source.text }}</p>
          <p v-else class="source-card__quote source-card__quote--empty">无正文摘要</p>

          <button
            v-if="source.text"
            type="button"
            class="source-card__copy"
            @click.stop="copySnippet(source.text, source.index)"
          >
            <el-icon class="w-3 h-3">
              <component :is="copiedIndex === source.index ? Check : DocumentCopy" />
            </el-icon>
            <span>{{ copiedIndex === source.index ? '已复制' : '复制摘录' }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import type { Source } from '@/types/models'
import { ArrowRight, DocumentCopy, Check } from '@/components/icons'

const props = defineProps<{
  sources?: Source[]
}>()

const expandedSet = ref<Set<number>>(new Set())
const copiedIndex = ref<number | null>(null)
let copyTimer: ReturnType<typeof setTimeout> | null = null

function isExpanded(index: number | undefined): boolean {
  if (index == null) return false
  return expandedSet.value.has(index)
}

function toggle(index: number | undefined): void {
  if (index == null) return
  const next = new Set(expandedSet.value)
  if (next.has(index)) {
    next.delete(index)
  } else {
    next.add(index)
  }
  expandedSet.value = next
}

function expand(index: number): void {
  const next = new Set(expandedSet.value)
  next.add(index)
  expandedSet.value = next
}

function copySnippet(text: string, index: number): void {
  if (!navigator?.clipboard) return
  navigator.clipboard.writeText(text).then(() => {
    copiedIndex.value = index
    if (copyTimer) clearTimeout(copyTimer)
    copyTimer = setTimeout(() => { copiedIndex.value = null }, 2000)
  }).catch(() => {})
}

watch(() => props.sources, () => { expandedSet.value = new Set() })
defineExpose({ expand })
</script>

<!--
  样式说明：本项目未启用 Tailwind preflight（global.css 只有 @tailwind utilities），
  因此来源卡样式在 scoped 纯 CSS 中显式声明，不依赖工具类。视觉规范：
  无边框、无色条——卡片与画布完全同色，仅靠序号/页码徽章与排版区分层次，
  hover 时以极轻的底色提示可点。令牌取自 variables.css。
-->
<style scoped>
.source-card {
  border-radius: var(--radius-xl);
  background: var(--bg-primary);
  transition: background-color 0.2s ease;
}
.dark .source-card {
  background: #000000;
}
.source-card:hover {
  background: color-mix(in srgb, var(--bg-primary) 97%, var(--text-primary));
}

/* 触发按钮：剥掉 UA 原生皮肤，恢复成普通容器 */
.source-card__trigger {
  -webkit-appearance: none;
  appearance: none;
  border: 0;
  background: transparent;
  font: inherit;
  color: inherit;
  width: 100%;
  display: flex;
  align-items: center;
  text-align: left;
  cursor: pointer;
  padding: 0;
}
.source-card__trigger:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: -2px;
  border-radius: var(--radius-xl);
}
.dark .source-card__trigger:focus-visible {
  outline-color: rgba(255, 255, 255, 0.7);
}

/* 内容区 */
.source-card__content {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  flex: 1;
  min-width: 0;
  padding: 0.625rem 0.5rem 0.625rem 0.875rem;
}
.source-card__index {
  flex-shrink: 0;
  min-width: 20px;
  height: 20px;
  padding: 0 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  background: var(--surface-card);
  color: var(--text-primary);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px;
  font-weight: 600;
}
.dark .source-card__index {
  border-color: rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.05);
  color: #d4d4d8;
}
.source-card__name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12.5px;
  font-weight: 500;
  line-height: 1.25;
  letter-spacing: -0.01em;
  color: var(--text-primary);
}
.dark .source-card__name {
  color: #e4e4e7;
}
.source-card__name--unknown {
  color: var(--text-muted);
  font-style: italic;
}
.source-card__page {
  flex-shrink: 0;
  padding: 2px 6px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-xs);
  background: var(--surface-card);
  color: var(--text-muted);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px;
  line-height: 1;
}
.dark .source-card__page {
  border-color: rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.05);
  color: #a1a1aa;
}

/* 右侧状态箭头（唯一展开指示） */
.source-card__cue {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  padding: 0 0.875rem;
  color: var(--text-muted);
  transition: color 0.2s ease;
}
.dark .source-card__cue {
  color: #a1a1aa;
}
.source-card__trigger:hover .source-card__cue {
  color: var(--text-primary);
}
.dark .source-card__trigger:hover .source-card__cue {
  color: #e4e4e7;
}
.source-card__arrow {
  flex-shrink: 0;
  transition: transform 0.2s ease;
}
.source-card--open .source-card__arrow {
  transform: rotate(90deg);
}

/* 展开正文：与画布同色，左对齐文件名起始位置 */
.source-card__body {
  padding: 0 3.25rem 0.75rem;
}
.source-card__body-main {
  min-width: 0;
}
.source-card__quote {
  font-size: 12.5px;
  line-height: 1.65;
  color: var(--text-secondary);
  overflow-wrap: break-word;
}
.dark .source-card__quote {
  color: #d4d4d8;
}
.source-card__quote--empty {
  color: var(--text-muted);
  font-style: italic;
}

/* 复制摘录按钮 */
.source-card__copy {
  -webkit-appearance: none;
  appearance: none;
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  margin-top: 0.625rem;
  padding: 2px 8px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-xs);
  background: transparent;
  color: var(--text-muted);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px;
  line-height: 1.4;
  cursor: pointer;
  transition: color 0.2s ease, background-color 0.2s ease, border-color 0.2s ease;
}
.dark .source-card__copy {
  border-color: rgba(255, 255, 255, 0.1);
  color: #a1a1aa;
}
.source-card__copy:hover {
  color: var(--text-primary);
  background: color-mix(in srgb, var(--text-primary) 4%, transparent);
}
.dark .source-card__copy:hover {
  color: #e4e4e7;
  background: rgba(255, 255, 255, 0.1);
}
.source-card__copy:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 1px;
}
.dark .source-card__copy:focus-visible {
  outline-color: rgba(255, 255, 255, 0.7);
}
</style>
