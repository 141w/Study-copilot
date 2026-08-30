import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock the api module
vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

// Mock chat store to avoid circular dependency
vi.mock('@/stores/chat', () => ({
  useChatStore: () => ({
    config: {
      provider: '',
      modelName: '',
      temperature: 0.7,
      maxTokens: 2048,
      baseUrl: '',
    },
  }),
}))

import { setActivePinia, createPinia } from 'pinia'
import { useNoteStore } from '@/stores/note'
import api from '@/services/api'

describe('Note Store', () => {
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useNoteStore()
    vi.clearAllMocks()
    localStorage.clear()
  })

  const mockNotes = [
    { id: '1', title: 'Note 1', content: 'Content 1', tags: ['tag1', 'tag2'], course_space_id: 'c1', note_type: 'markdown' },
    { id: '2', title: 'Note 2', content: 'Content 2', tags: [{ id: '1', name: 'tag1' }], course_space_id: 'c1', note_type: 'ai' },
    { id: '3', title: 'Note 3', content: 'Content 3', tags: ['tag3'], course_space_id: 'c2', note_type: 'markdown' },
  ]

  it('has correct initial state', () => {
    expect(store.notes).toEqual([])
    expect(store.currentNote).toBeNull()
    expect(store.loading).toBe(false)
    expect(store.filterCourseId).toBeNull()
    expect(store.filterTag).toBeNull()
    expect(store.searchQuery).toBe('')
  })

  it('fetchNotes loads notes from API', async () => {
    api.get.mockResolvedValue({ data: mockNotes })

    await store.fetchNotes()

    expect(store.notes).toHaveLength(3)
    expect(api.get).toHaveBeenCalledWith('/notes', { params: {} })
  })

  it('fetchNotes sets loading state', async () => {
    let resolvePromise
    const promise = new Promise(resolve => { resolvePromise = resolve })
    api.get.mockReturnValue(promise)

    const fetchPromise = store.fetchNotes()

    expect(store.loading).toBe(true)
    resolvePromise({ data: mockNotes })
    await fetchPromise
    expect(store.loading).toBe(false)
  })

  it('fetchNote loads single note', async () => {
    api.get.mockResolvedValue({ data: mockNotes[0] })

    const result = await store.fetchNote('1')

    expect(store.currentNote).toEqual(mockNotes[0])
    expect(result).toEqual(mockNotes[0])
    expect(api.get).toHaveBeenCalledWith('/notes/1')
  })

  it('createNote adds note to list', async () => {
    const newNote = { id: '4', title: 'New Note', content: 'New content', tags: [], note_type: 'markdown' }
    api.post.mockResolvedValue({ data: newNote })

    const result = await store.createNote({ title: 'New Note', content: 'New content' })

    expect(store.notes).toHaveLength(1)
    expect(store.notes[0]).toEqual(newNote)
    expect(api.post).toHaveBeenCalledWith('/notes', { title: 'New Note', content: 'New content' })
  })

  it('updateNote modifies existing note', async () => {
    store.notes = [...mockNotes]
    const updated = { ...mockNotes[0], title: 'Updated Title' }
    api.put.mockResolvedValue({ data: updated })

    await store.updateNote('1', { title: 'Updated Title' })

    expect(store.notes[0].title).toBe('Updated Title')
    expect(api.put).toHaveBeenCalledWith('/notes/1', { title: 'Updated Title' })
  })

  it('deleteNote removes note from list', async () => {
    store.notes = [...mockNotes]
    api.delete.mockResolvedValue({})

    await store.deleteNote('1')

    expect(store.notes).toHaveLength(2)
    expect(store.notes.find(n => n.id === '1')).toBeUndefined()
  })

  it('filteredNotes filters by course', () => {
    store.notes = [...mockNotes]
    store.setFilterCourse('c2')

    expect(store.filteredNotes).toHaveLength(1)
    expect(store.filteredNotes[0].id).toBe('3')
  })

  it('filteredNotes filters by tag', () => {
    store.notes = [...mockNotes]
    store.setFilterTag('tag1')

    expect(store.filteredNotes).toHaveLength(2)
  })

  it('filteredNotes searches by title and content', () => {
    store.notes = [...mockNotes]
    store.setSearchQuery('Note 2')

    expect(store.filteredNotes).toHaveLength(1)
    expect(store.filteredNotes[0].id).toBe('2')
  })

  it('allTags returns unique sorted tag names', () => {
    store.notes = [
      { tags: ['beta', 'alpha'] },
      { tags: [{ id: '1', name: 'gamma' }] },
      { tags: ['alpha'] },
    ]

    expect(store.allTags).toEqual(['alpha', 'beta', 'gamma'])
  })

  it('clearFilters resets all filters', () => {
    store.filterCourseId = 'c1'
    store.filterTag = 'tag1'
    store.searchQuery = 'query'
    store.clearFilters()

    expect(store.filterCourseId).toBeNull()
    expect(store.filterTag).toBeNull()
    expect(store.searchQuery).toBe('')
  })

  it('selectNote sets currentNote', () => {
    store.selectNote(mockNotes[0])
    expect(store.currentNote).toEqual(mockNotes[0])
  })

  describe('SWR cache', () => {
    beforeEach(() => {
      vi.useFakeTimers()
    })

    afterEach(() => {
      vi.useRealTimers()
    })

    it('returns cached data when fetched within 30s (no API call)', async () => {
      api.get.mockResolvedValue({ data: mockNotes })

      await store.fetchNotes()
      expect(api.get).toHaveBeenCalledTimes(1)

      await store.fetchNotes()
      expect(api.get).toHaveBeenCalledTimes(1) // Still 1, not 2
    })

    it('refreshes from API when cache is stale (>30s)', async () => {
      api.get.mockResolvedValue({ data: mockNotes })

      await store.fetchNotes()
      expect(api.get).toHaveBeenCalledTimes(1)

      vi.advanceTimersByTime(35000)

      await store.fetchNotes()
      expect(api.get).toHaveBeenCalledTimes(2)
    })

    it('createNote invalidates cache', async () => {
      api.get.mockResolvedValue({ data: mockNotes })
      api.post.mockResolvedValue({ data: { id: '4', title: 'New', content: '', tags: [], note_type: 'markdown' } })

      await store.fetchNotes()
      expect(api.get).toHaveBeenCalledTimes(1)

      await store.createNote({ title: 'New', content: 'New content' })

      // Cache invalidated, next fetch should call API
      await store.fetchNotes()
      expect(api.get).toHaveBeenCalledTimes(2)
    })

    it('deleteNote invalidates cache', async () => {
      store.notes = [...mockNotes]
      api.delete.mockResolvedValue({})

      await store.deleteNote('1')

      // lastFetched reset → next fetch calls API
      await store.fetchNotes()
      expect(api.get).toHaveBeenCalledTimes(1)
    })
  })
})
