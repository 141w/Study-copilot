import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../services/api'

export const useCourseStore = defineStore('course', () => {
  const courses = ref([])
  const currentCourse = ref(null)
  const loading = ref(false)

  async function fetchCourses() {
    loading.value = true
    try {
      const response = await api.get('/courses')
      courses.value = response.data
    } catch (error) {
      console.error('Error fetching courses:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function fetchCourse(courseId) {
    loading.value = true
    try {
      const response = await api.get(`/courses/${courseId}`)
      currentCourse.value = response.data
      return response.data
    } catch (error) {
      console.error('Error fetching course:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function createCourse(data) {
    loading.value = true
    try {
      const response = await api.post('/courses', data)
      courses.value.unshift(response.data)
      return response.data
    } catch (error) {
      console.error('Error creating course:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function updateCourse(courseId, data) {
    loading.value = true
    try {
      const response = await api.put(`/courses/${courseId}`, data)
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

  async function deleteCourse(courseId) {
    try {
      await api.delete(`/courses/${courseId}`)
      courses.value = courses.value.filter(c => c.id !== courseId)
    } catch (error) {
      console.error('Error deleting course:', error)
      throw error
    }
  }

  async function fetchCourseDocuments(courseId) {
    try {
      const response = await api.get(`/courses/${courseId}/documents`)
      return response.data
    } catch (error) {
      console.error('Error fetching course documents:', error)
      throw error
    }
  }

  async function addDocumentToCourse(courseId, documentId) {
    try {
      const response = await api.post(`/courses/${courseId}/documents`, { document_id: documentId })
      return response.data
    } catch (error) {
      console.error('Error adding document to course:', error)
      throw error
    }
  }

  async function removeDocumentFromCourse(courseId, documentId) {
    try {
      await api.delete(`/courses/${courseId}/documents/${documentId}`)
    } catch (error) {
      console.error('Error removing document from course:', error)
      throw error
    }
  }

  function selectCourse(course) {
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
