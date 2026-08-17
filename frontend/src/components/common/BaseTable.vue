<template>
  <div class="base-table-wrapper">
    <div class="overflow-x-auto">
      <table class="base-table">
        <thead>
          <tr>
            <th
              v-for="column in columns"
              :key="column.key"
              class="base-table-th"
              :style="{ width: column.width }"
            >
              <div class="flex items-center gap-2">
                <span>{{ column.label }}</span>
                <button
                  v-if="column.sortable"
                  @click="toggleSort(column.key)"
                  class="base-table-sort-btn"
                  :class="{ 'text-[var(--color-primary)]': sortKey === column.key }"
                >
                  <svg
                    class="w-4 h-4 transition-transform"
                    :class="{ 'rotate-180': sortKey === column.key && sortOrder === 'desc' }"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
                  </svg>
                </button>
              </div>
            </th>
            <th v-if="$slots.actions" class="base-table-th w-24">
              操作
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td :colspan="columns.length + ($slots.actions ? 1 : 0)" class="base-table-empty">
              <div class="flex items-center justify-center gap-2 py-8">
                <LoadingSpinner size="sm" />
                <span class="text-[var(--text-muted)]">加载中...</span>
              </div>
            </td>
          </tr>
          <tr v-else-if="data.length === 0">
            <td :colspan="columns.length + ($slots.actions ? 1 : 0)" class="base-table-empty">
              <slot name="empty">
                <div class="py-8 text-center text-[var(--text-muted)]">暂无数据</div>
              </slot>
            </td>
          </tr>
          <tr
            v-else
            v-for="(row, index) in sortedData"
            :key="row[keyField] || index"
            class="base-table-row"
          >
            <td
              v-for="column in columns"
              :key="column.key"
              class="base-table-td"
            >
              <slot :name="`cell-${column.key}`" :row="row" :value="row[column.key]">
                {{ row[column.key] }}
              </slot>
            </td>
            <td v-if="$slots.actions" class="base-table-td">
              <slot name="actions" :row="row" />
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div v-if="pagination" class="base-table-pagination">
      <span class="text-sm text-[var(--text-muted)]">
        共 {{ pagination.total }} 条
      </span>
      <div class="flex items-center gap-2">
        <button
          @click="$emit('page-change', pagination.page - 1)"
          :disabled="pagination.page <= 1"
          class="base-table-page-btn"
        >
          上一页
        </button>
        <span class="text-sm text-[var(--text-secondary)]">
          {{ pagination.page }} / {{ Math.ceil(pagination.total / pagination.pageSize) }}
        </span>
        <button
          @click="$emit('page-change', pagination.page + 1)"
          :disabled="pagination.page >= Math.ceil(pagination.total / pagination.pageSize)"
          class="base-table-page-btn"
        >
          下一页
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import LoadingSpinner from './LoadingSpinner.vue'

interface Column {
  key: string
  label: string
  width?: string
  sortable?: boolean
}

interface Pagination {
  page: number
  pageSize: number
  total: number
}

interface Props {
  columns: Column[]
  data: Record<string, any>[]
  keyField?: string
  loading?: boolean
  pagination?: Pagination
}

const props = withDefaults(defineProps<Props>(), {
  keyField: 'id',
  loading: false
})

defineEmits<{
  'page-change': [page: number]
}>()

const sortKey = ref<string>('')
const sortOrder = ref<'asc' | 'desc'>('asc')

function toggleSort(key: string) {
  if (sortKey.value === key) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortOrder.value = 'asc'
  }
}

const sortedData = computed(() => {
  if (!sortKey.value) return props.data

  return [...props.data].sort((a, b) => {
    const aVal = a[sortKey.value]
    const bVal = b[sortKey.value]

    if (aVal === bVal) return 0
    if (aVal === null || aVal === undefined) return 1
    if (bVal === null || bVal === undefined) return -1

    const result = aVal < bVal ? -1 : 1
    return sortOrder.value === 'asc' ? result : -result
  })
})
</script>

<style scoped>
.base-table-wrapper {
  width: 100%;
  overflow: hidden;
  border-radius: var(--radius-xl);
  border: 1px solid var(--border-default);
  background-color: var(--surface-card);
}

.base-table {
  width: 100%;
  border-collapse: collapse;
}

.base-table-th {
  padding: var(--spacing-sm) var(--spacing-md);
  text-align: left;
  font-size: var(--font-size-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  background-color: var(--bg-secondary);
  border-bottom: 1px solid var(--border-default);
}

.base-table-sort-btn {
  padding: 2px;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  transition: color var(--transition-fast);
}

.base-table-sort-btn:hover {
  color: var(--text-secondary);
}

.base-table-row {
  border-bottom: 1px solid var(--border-default);
  transition: background-color var(--transition-fast);
}

.base-table-row:last-child {
  border-bottom: none;
}

.base-table-row:hover {
  background-color: var(--bg-hover);
}

.base-table-td {
  padding: var(--spacing-sm) var(--spacing-md);
  font-size: var(--font-size-sm);
  color: var(--text-primary);
}

.base-table-empty {
  padding: var(--spacing-lg);
  text-align: center;
}

.base-table-pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-sm) var(--spacing-md);
  border-top: 1px solid var(--border-default);
  background-color: var(--bg-secondary);
}

.base-table-page-btn {
  padding: var(--spacing-xs) var(--spacing-sm);
  font-size: var(--font-size-sm);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  background-color: var(--surface-card);
  color: var(--text-secondary);
  transition: all var(--transition-fast);
}

.base-table-page-btn:hover:not(:disabled) {
  border-color: var(--border-focus);
  color: var(--color-primary);
}

.base-table-page-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
