<template>
  <div class="base-list-wrapper">
    <!-- Loading state -->
    <div v-if="loading" class="base-list-loading">
      <LoadingSpinner size="md" />
      <span class="text-[var(--text-muted)]">{{ loadingText }}</span>
    </div>

    <!-- Empty state -->
    <div v-else-if="items.length === 0" class="base-list-empty">
      <slot name="empty">
        <div class="base-list-empty-icon">
          <svg class="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
          </svg>
        </div>
        <p class="text-[var(--text-muted)]">{{ emptyText }}</p>
      </slot>
    </div>

    <!-- List content -->
    <div v-else class="base-list">
      <div
        v-for="(item, index) in items"
        :key="item[keyField] || index"
        class="base-list-item"
        :class="{ 'base-list-item-hover': hoverable }"
        @click="hoverable && $emit('item-click', item)"
      >
        <slot :item="item" :index="index">
          <div class="base-list-item-content">
            <div v-if="item.icon" class="base-list-item-icon">
              <component :is="item.icon" />
            </div>
            <div class="base-list-item-body">
              <div class="base-list-item-title">{{ item.title }}</div>
              <div v-if="item.description" class="base-list-item-description">
                {{ item.description }}
              </div>
            </div>
            <div v-if="item.meta" class="base-list-item-meta">
              {{ item.meta }}
            </div>
          </div>
        </slot>
      </div>
    </div>

    <!-- Load more -->
    <div v-if="hasMore && !loading" class="base-list-load-more">
      <button
        @click="$emit('load-more')"
        class="base-list-load-more-btn"
      >
        {{ loadMoreText }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import LoadingSpinner from './LoadingSpinner.vue'

interface Props {
  items: Record<string, any>[]
  keyField?: string
  loading?: boolean
  loadingText?: string
  emptyText?: string
  hoverable?: boolean
  hasMore?: boolean
  loadMoreText?: string
}

withDefaults(defineProps<Props>(), {
  keyField: 'id',
  loading: false,
  loadingText: '加载中...',
  emptyText: '暂无数据',
  hoverable: false,
  hasMore: false,
  loadMoreText: '加载更多'
})

defineEmits<{
  'item-click': [item: Record<string, any>]
  'load-more': []
}>()
</script>

<style scoped>
.base-list-wrapper {
  width: 100%;
}

.base-list-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-md);
  padding: var(--spacing-2xl);
}

.base-list-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-md);
  padding: var(--spacing-2xl);
}

.base-list-empty-icon {
  color: var(--text-muted);
  opacity: 0.5;
}

.base-list {
  display: flex;
  flex-direction: column;
}

.base-list-item {
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--border-default);
  transition: background-color var(--transition-fast);
}

.base-list-item:last-child {
  border-bottom: none;
}

.base-list-item-hover {
  cursor: pointer;
}

.base-list-item-hover:hover {
  background-color: var(--bg-hover);
}

.base-list-item-content {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.base-list-item-icon {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-lg);
  background-color: var(--bg-tertiary);
  color: var(--text-secondary);
}

.base-list-item-body {
  flex: 1;
  min-width: 0;
}

.base-list-item-title {
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--text-primary);
}

.base-list-item-description {
  font-size: var(--font-size-xs);
  color: var(--text-muted);
  margin-top: var(--spacing-xs);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.base-list-item-meta {
  flex-shrink: 0;
  font-size: var(--font-size-xs);
  color: var(--text-muted);
}

.base-list-load-more {
  padding: var(--spacing-md);
  text-align: center;
}

.base-list-load-more-btn {
  padding: var(--spacing-sm) var(--spacing-lg);
  font-size: var(--font-size-sm);
  color: var(--color-primary);
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-lg);
  background-color: transparent;
  transition: all var(--transition-fast);
}

.base-list-load-more-btn:hover {
  background-color: var(--color-primary-light);
}
</style>
