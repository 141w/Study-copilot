import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../services/api'
import type { Note } from '../types/models'

/** 后端列表接口 tags 为 string[]，详情为对象数组——这里统一兼容两种形态 */
export type NoteTag = string | { id?: string; name?: string }

export interface NoteDetail extends Omit<Note, 'tags'> {
  tags: NoteTag[]
}

export interface NoteCreatePayload {
  title: string
  content?: string
  course_id?: string | null
  course_space_id?: string | null
  note_type?: string
  tags?: string[]
}

export interface NoteUpdatePayload extends Partial<NoteCreatePayload> {
  is_pinned?: boolean
}

function tagNames(note: { tags?: NoteTag[] }): string[] {
  if (!note.tags) return []
  return note.tags.map(t => (typeof t === 'string' ? t : t?.name)).filter(Boolean) as string[]
}

export const useNoteStore = defineStore('note', () => {
  const notes = ref<NoteDetail[]>([])
  const currentNote = ref<NoteDetail | null>(null)
  const loading = ref(false)
  const filterCourseId = ref<string | null>(null)
  const filterTag = ref<string | null>(null)
  const searchQuery = ref('')

  const filteredNotes = computed<NoteDetail[]>(() => {
    let result = notes.value

    if (filterCourseId.value) {
      result = result.filter(n => n.course_space_id === filterCourseId.value)
    }

    if (filterTag.value) {
      result = result.filter(n => tagNames(n).includes(filterTag.value as string))
    }

    if (searchQuery.value.trim()) {
      const query = searchQuery.value.toLowerCase()
      result = result.filter(
        n =>
          (n.title && n.title.toLowerCase().includes(query)) ||
          (n.content && n.content.toLowerCase().includes(query))
      )
    }

    return result
  })

  const allTags = computed<string[]>(() => {
    const tagSet = new Set<string>()
    notes.value.forEach(n => {
      tagNames(n).forEach(t => tagSet.add(t))
    })
    return Array.from(tagSet).sort()
  })

  async function fetchNotes(params: Record<string, unknown> = {}): Promise<void> {
    loading.value = true
    try {
      const response = await api.get<NoteDetail[]>('/notes', { params })
      notes.value = response.data
    } catch (error) {
      console.error('Error fetching notes:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function fetchNote(noteId: string): Promise<NoteDetail> {
    loading.value = true
    try {
      const response = await api.get<NoteDetail>(`/notes/${noteId}`)
      currentNote.value = response.data
      return response.data
    } catch (error) {
      console.error('Error fetching note:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function createNote(data: NoteCreatePayload): Promise<NoteDetail> {
    loading.value = true
    try {
      const response = await api.post<NoteDetail>('/notes', data)
      notes.value.unshift(response.data)
      return response.data
    } catch (error) {
      console.error('Error creating note:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function updateNote(noteId: string, data: NoteUpdatePayload): Promise<NoteDetail> {
    loading.value = true
    try {
      const response = await api.put<NoteDetail>(`/notes/${noteId}`, data)
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

  async function deleteNote(noteId: string): Promise<void> {
    try {
      await api.delete(`/notes/${noteId}`)
      notes.value = notes.value.filter(n => n.id !== noteId)
    } catch (error) {
      console.error('Error deleting note:', error)
      throw error
    }
  }

  function setFilterCourse(courseId: string | null): void {
    filterCourseId.value = courseId
  }

  function setFilterTag(tag: string | null): void {
    filterTag.value = tag
  }

  function setSearchQuery(query: string): void {
    searchQuery.value = query
  }

  function clearFilters(): void {
    filterCourseId.value = null
    filterTag.value = null
    searchQuery.value = ''
  }

  function selectNote(note: NoteDetail | null): void {
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
