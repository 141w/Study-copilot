import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../services/api'

export interface OpenMAICClassroom {
  course_id: string
  title: string
  url: string
  created_at: string
}

export const useOpenMAICStore = defineStore('openmaic', () => {
  const classrooms = ref<OpenMAICClassroom[]>([])
  const loading = ref(false)

  async function fetchClassrooms(): Promise<void> {
    // 修复（批次8）：原守卫条件反了（length>0 && loading 才跳过）——
    // 加载完成后每次挂载都会绕过缓存重复请求。正确语义：进行中或已有数据即跳过
    if (loading.value || classrooms.value.length > 0) return
    loading.value = true
    try {
      const { data } = await api.get('/integrations/openmaic/classrooms')
      classrooms.value = data.classrooms || []
    }
    catch {
      classrooms.value = []
    }
    finally {
      loading.value = false
    }
  }

  function getClassroom(courseId: string): OpenMAICClassroom | undefined {
    return classrooms.value.find(c => c.course_id === courseId)
  }

  return { classrooms, loading, fetchClassrooms, getClassroom }
})
