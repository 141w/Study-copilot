import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../services/api'

export interface OpenMAICClassroom {
  course_id: string
  title: string
  url: string
  created_at: string
}

export interface JobStatus {
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

export const useOpenMAICStore = defineStore('openmaic', () => {
  const classrooms = ref<OpenMAICClassroom[]>([])
  const loading = ref(false)
  const activeJobs = ref<Record<string, JobStatus>>({})

  async function fetchClassrooms(force = false): Promise<void> {
    if (!force && (loading.value || classrooms.value.length > 0)) return
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

  async function pollJobStatus(jobId: string): Promise<JobStatus> {
    const { data } = await api.get(`/integrations/openmaic/classroom/${jobId}/status`)
    activeJobs.value[jobId] = data
    if (data.done) {
      await fetchClassrooms(true)
    }
    return data
  }

  return { classrooms, loading, activeJobs, fetchClassrooms, getClassroom, pollJobStatus }
})
