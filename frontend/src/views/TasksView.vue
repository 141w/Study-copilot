<template>
  <div class="max-w-4xl mx-auto px-6 py-8">
    <h1 class="text-2xl font-semibold text-[var(--text-primary)] mb-6">后台任务</h1>
    <TaskPanel />
    <!-- 批次6：请求进行中先铺骨架，防止白屏；与空态互斥（loaded 之前不闪"暂无"） -->
    <SkeletonList v-if="!loaded" variant="rows" :count="3" />
    <!-- P3-6：空态接入 EmptyState 组件（与其他页统一），加载中不闪空态 -->
    <EmptyState
      v-if="!hasTasks && loaded"
      size="lg"
      :icon="Reading"
      message="暂无后台任务"
      hint="批量操作（如文档转换、批量导出）会在这里显示实时进度"
    >
      <el-button type="primary" @click="$router.push('/upload')">去上传文档</el-button>
    </EmptyState>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Reading } from '@/components/icons'
import TaskPanel from '../components/TaskPanel.vue'
import EmptyState from '../components/common/EmptyState.vue'
import SkeletonList from '../components/common/SkeletonList.vue'
import api from '../services/api'

const hasTasks = ref(false)
const loaded = ref(false)

onMounted(async () => {
  try {
    const resp = await api.get('/tasks', { params: { limit: 1 } })
    hasTasks.value = (resp.data.tasks || []).length > 0
  } catch {
    // ignore
  } finally {
    loaded.value = true
  }
})
</script>
