import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../services/api'
import type { Course } from '../types/models'

/** 创建/更新课程时前端提交的字段 */
export interface CoursePayload {
  name: string
  description?: string
}

export const useCourseStore = defineStore('course', () => {
  const courses = ref<Course[]>([])
  const currentCourse = ref<Course | null>(null)
  const loading = ref(false)

  async function fetchCourses(): Promise<void> {
    loading.value = true
    try {
      const response = await api.get<Course[]>('/courses')
      courses.value = response.data
    } catch (error) {
      console.error('Error fetching courses:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function fetchCourse(courseId: string): Promise<Course> {
    loading.value = true
    try {
      const response = await api.get<Course>(`/courses/${courseId}`)
      currentCourse.value = response.data
      return response.data
    } catch (error) {
      console.error('Error fetching course:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function createCourse(data: CoursePayload): Promise<Course> {
    loading.value = true
    try {
      const response = await api.post<Course>('/courses', data)
      courses.value.unshift(response.data)
      return response.data
    } catch (error) {
      console.error('Error creating course:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function updateCourse(courseId: string, data: Partial<CoursePayload>): Promise<Course> {
    loading.value = true
    try {
      const response = await api.put<Course>(`/courses/${courseId}`, data)
      const idx = courses.value.findIndex(c => c.id === courseId)
      if (idx !== -1) {
        courses.value[idx] = response.data
      }
      if (currentCourse.value?.id === courseId) {
        currentCourse.value = response.data
      }
      return response.data
    } catch (error) {
      console.error('Error updating course:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function deleteCourse(courseId: string): Promise<void> {
    try {
      await api.delete(`/courses/${courseId}`)
      courses.value = courses.value.filter(c => c.id !== courseId)
    } catch (error) {
      console.error('Error deleting course:', error)
      throw error
    }
  }

  async function fetchCourseDocuments(courseId: string): Promise<Course[]> {
    try {
      const response = await api.get<Course[]>(`/courses/${courseId}/documents`)
      return response.data
    } catch (error) {
      console.error('Error fetching course documents:', error)
      throw error
    }
  }

  async function addDocumentToCourse(courseId: string, documentId: string): Promise<any> {
    try {
      const response = await api.post(`/courses/${courseId}/documents`, { document_id: documentId })
      return response.data
    } catch (error) {
      console.error('Error adding document to course:', error)
      throw error
    }
  }

  async function removeDocumentFromCourse(courseId: string, documentId: string): Promise<void> {
    try {
      await api.delete(`/courses/${courseId}/documents/${documentId}`)
    } catch (error) {
      console.error('Error removing document from course:', error)
      throw error
    }
  }

  function selectCourse(course: Course | null): void {
    currentCourse.value = course
  }

  return {
    courses,
    currentCourse,
    loading,
    fetchCourses,
    fetchCourse,
    createCourse,
    updateCourse,
    deleteCourse,
    fetchCourseDocuments,
    addDocumentToCourse,
    removeDocumentFromCourse,
    selectCourse
  }
})
