import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../services/api'

export interface ClassroomItem {
  course_id: string
  title: string
  url: string
  created_at: string
}

export interface ClassroomJobStatus {
  job_id: string
  status: string
  step: string
  progress: number
  message: string
  scenes_generated: number
  total_scenes: number
  done: boolean
  result?: {
    classroomId?: string
    url?: string
    title?: string
    [key: string]: any
  }
  sync_result?: any
}

export const useClassroomStore = defineStore('classroom', () => {
  const classrooms = ref<ClassroomItem[]>([])
  const loading = ref(false)
  const activeJobs = ref<Record<string, ClassroomJobStatus>>({})

  async function fetchClassrooms(force = false): Promise<void> {
    if (!force && (loading.value || classrooms.value.length > 0)) return
    loading.value = true
    try {
      const { data } = await api.get('/classroom/list')
      classrooms.value = data.classrooms || []
    }
    catch {
      classrooms.value = []
    }
    finally {
      loading.value = false
    }
  }

  function getClassroom(courseId: string): ClassroomItem | undefined {
    return classrooms.value.find(c => c.course_id === courseId)
  }

  async function pollJobStatus(jobId: string): Promise<ClassroomJobStatus> {
    const { data } = await api.get(`/classroom/${jobId}/status`)
    activeJobs.value[jobId] = data
    if (data.done) {
      await fetchClassrooms(true)
    }
    return data
  }

  return { classrooms, loading, activeJobs, fetchClassrooms, getClassroom, pollJobStatus }
})
