<template>
  <div
    ref="cardEl"
    class="card p-5 hover:border-[var(--color-primary)] border-2 border-transparent transition-all cursor-pointer group"
    @click="$emit('click', course)"
  >
    <div class="flex items-start justify-between mb-3">
      <div class="w-10 h-10 bg-[var(--color-accent-light, #f3f0ff)] rounded-lg flex items-center justify-center flex-shrink-0 group-hover:bg-[var(--color-accent-light, #f3f0ff)] transition-colors">
        <el-icon class="w-5 h-5 text-[var(--color-accent)]"><Reading /></el-icon>
      </div>
      <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          @click.stop="$emit('edit', course)"
          class="p-1.5 text-[var(--text-muted)] hover:text-[var(--color-info)] hover:bg-[var(--color-info-light)] rounded transition-colors"
          title="编辑课程"
        >
          <el-icon class="w-4 h-4"><Edit /></el-icon>
        </button>
        <button
          @click.stop="$emit('delete', course)"
          class="p-1.5 text-[var(--text-muted)] hover:text-[var(--color-error)] hover:bg-[var(--color-error-light)] rounded transition-colors"
          title="删除课程"
        >
          <el-icon class="w-4 h-4"><Delete /></el-icon>
        </button>
      </div>
    </div>

    <h3 class="font-semibold text-[var(--text-primary)] mb-1 truncate">{{ course.name }}</h3>
    <p v-if="course.description" class="text-sm text-[var(--text-muted)] line-clamp-2 mb-3">{{ course.description }}</p>

    <div class="flex items-center gap-3 mt-auto text-xs text-[var(--text-muted)]">
      <span class="flex items-center gap-1">
        <el-icon class="w-3.5 h-3.5"><Tickets /></el-icon>
        {{ course.document_count || 0 }} 份文档
      </span>
      <span v-if="course.note_count" class="flex items-center gap-1">
        <el-icon class="w-3.5 h-3.5"><Edit /></el-icon>
        {{ course.note_count }} 条笔记
      </span>
      <span v-if="course.color" class="ml-auto">
        <span class="inline-block w-3 h-3 rounded-full" :style="{ backgroundColor: course.color }"></span>
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Reading, Edit, Delete, Tickets } from '@element-plus/icons-vue'
import type { Course } from '../types/models'

defineProps<{
  course: Course
}>()

defineEmits<{
  click: [course: Course]
  edit: [course: Course]
  delete: [course: Course]
}>()
</script>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
