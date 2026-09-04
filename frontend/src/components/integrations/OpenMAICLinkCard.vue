<template>
  <div class="space-y-3">
    <!-- 空状态 -->
    <div
      v-if="classrooms.length === 0"
      class="text-center py-8 text-[var(--text-muted)]"
    >
      <el-icon class="text-3xl mb-2"><VideoPlay /></el-icon>
      <p class="text-sm">暂无生成过的课堂</p>
      <p class="text-xs mt-1">从课程或文档页面点击"生成课堂"开始</p>
    </div>

    <!-- 课堂列表 -->
    <div
      v-for="c in classrooms"
      :key="c.course_id"
      class="border border-[var(--border-default)] rounded-lg p-4 hover:border-[var(--border-hover)] transition-colors"
    >
      <div class="flex items-start gap-3">
        <div class="w-10 h-10 rounded-lg bg-[var(--color-primary-light)] flex items-center justify-center flex-shrink-0">
          <el-icon class="text-[var(--color-primary)] text-lg"><VideoPlay /></el-icon>
        </div>
        <div class="flex-1 min-w-0">
          <h4 class="text-sm font-medium text-[var(--text-primary)] truncate">{{ c.title }}</h4>
          <p class="text-xs text-[var(--text-muted)] mt-0.5">
            {{ formatDate(c.created_at) }}
          </p>
        </div>
        <div class="flex gap-1">
          <el-button
            v-if="c.url"
            size="small"
            type="primary"
            text
            @click="openClassroom(c.url)"
          >
            进入课堂
          </el-button>
          <el-button
            size="small"
            text
            @click="copyUrl(c.url)"
          >
            复制链接
          </el-button>
        </div>
      </div>

      <!-- iframe 内嵌预览（展开后） -->
      <div v-if="expandedId === c.course_id && c.url" class="mt-3">
        <div class="relative w-full rounded-lg overflow-hidden border border-[var(--border-default)]" style="padding-bottom: 56.25%">
          <iframe
            :src="c.url"
            class="absolute inset-0 w-full h-full"
            frameborder="0"
            allow="autoplay; fullscreen"
            allowfullscreen
          />
        </div>
      </div>

      <div class="mt-2 flex justify-end">
        <el-button
          v-if="c.url"
          size="small"
          type="primary"
          link
          @click="toggleExpand(c.course_id)"
        >
          {{ expandedId === c.course_id ? '收起预览' : '预览课堂' }}
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { VideoPlay } from '@/components/icons'

export interface OpenMAICClassroom {
  course_id: string
  title: string
  url: string
  created_at: string
}

const props = defineProps<{
  classrooms: OpenMAICClassroom[]
}>()

const expandedId = ref<string | null>(null)

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('zh-CN', {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
    })
  }
  catch {
    return iso
  }
}

function openClassroom(url: string): void {
  window.open(url, '_blank')
}

async function copyUrl(url: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(url)
    ElMessage.success('链接已复制到剪贴板')
  }
  catch {
    ElMessage.error('复制失败')
  }
}

function toggleExpand(courseId: string): void {
  expandedId.value = expandedId.value === courseId ? null : courseId
}
</script>
