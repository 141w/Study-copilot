import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../services/api'

export const useNoteStore = defineStore('note', () => {
  const notes = ref([])
  const currentNote = ref(null)
  const loading = ref(false)
  const filterCourseId = ref(null)
  const filterTag = ref(null)
  const searchQuery = ref('')

  // Normalize a note's tags to string names (backend may return strings or {id,name} objects)
  function tagNames(note) {
    if (!note.tags) return []
    return note.tags.map(t => (typeof t === 'string' ? t : t?.name)).filter(Boolean)
  }

  const filteredNotes = computed(() => {
    let result = notes.value

    if (filterCourseId.value) {
      result = result.filter(n => n.course_space_id === filterCourseId.value)
    }

    if (filterTag.value) {
      result = result.filter(n => tagNames(n).includes(filterTag.value))
    }

    if (searchQuery.value.trim()) {
      const query = searchQuery.value.toLowerCase()
      result = result.filter(n =>
        (n.title && n.title.toLowerCase().includes(query)) ||
        (n.content && n.content.toLowerCase().includes(query))
      )
    }

    return result
  })

  const allTags = computed(() => {
    const tagSet = new Set()
    notes.value.forEach(n => {
      tagNames(n).forEach(t => tagSet.add(t))
    })
    return Array.from(tagSet).sort()
  })

  async function fetchNotes(params = {}) {
    loading.value = true
    try {
      const response = await api.get('/notes', { params })
      notes.value = response.data
    } catch (error) {
      console.error('Error fetching notes:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function fetchNote(noteId) {
    loading.value = true
    try {
      const response = await api.get(`/notes/${noteId}`)
      currentNote.value = response.data
      return response.data
    } catch (error) {
      console.error('Error fetching note:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function createNote(data) {
    loading.value = true
    try {
      const response = await api.post('/notes', data)
      notes.value.unshift(response.data)
      return response.data
    } catch (error) {
      console.error('Error creating note:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function updateNote(noteId, data) {
    loading.value = true
    try {
      const response = await api.put(`/notes/${noteId}`, data)
      const idx = notes.value.findIndex(n => n.id === noteId)
      if (idx !== -1) {
        notes.value[idx] = response.data
      }
      if (currentNote.value?.id === noteId) {
        currentNote.value = response.data
      }
      return response.data
    } catch (error) {
      console.error('Error updating note:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function deleteNote(noteId) {
    try {
      await api.delete(`/notes/${noteId}`)
      notes.value = notes.value.filter(n => n.id !== noteId)
    } catch (error) {
      console.error('Error deleting note:', error)
      throw error
    }
  }

  function setFilterCourse(courseId) {
    filterCourseId.value = courseId
  }

  function setFilterTag(tag) {
    filterTag.value = tag
  }

  function setSearchQuery(query) {
    searchQuery.value = query
  }

  function clearFilters() {
    filterCourseId.value = null
    filterTag.value = null
    searchQuery.value = ''
  }

  function selectNote(note) {
    currentNote.value = note
  }

  return {
    notes,
    currentNote,
    loading,
    filterCourseId,
    filterTag,
    searchQuery,
    filteredNotes,
    allTags,
    fetchNotes,
    fetchNote,
    createNote,
    updateNote,
    deleteNote,
    setFilterCourse,
    setFilterTag,
    setSearchQuery,
    clearFilters,
    selectNote
  }
})
