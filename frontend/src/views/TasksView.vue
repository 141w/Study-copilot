<template>
  <div class="max-w-4xl mx-auto px-6 py-8">
    <h1 class="text-2xl font-bold text-[var(--text-primary)] mb-6">后台任务</h1>
    <TaskPanel />
    <p v-if="!hasTasks" class="text-[var(--text-muted)] text-sm mt-4">暂无后台任务</p>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import TaskPanel from '../components/TaskPanel.vue'
import api from '../services/api'

const hasTasks = ref(false)

onMounted(async () => {
  try {
    const resp = await api.get('/tasks', { params: { limit: 1 } })
    hasTasks.value = (resp.data.tasks || []).length > 0
  } catch {
    // ignore
  }
})
</script>
