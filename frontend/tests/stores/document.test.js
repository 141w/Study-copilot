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

vi.mock('@/stores/toast', () => ({
  useToastStore: vi.fn(() => ({
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  })),
}))

import { setActivePinia, createPinia } from 'pinia'
import { useDocumentStore } from '@/stores/document'
import api from '@/services/api'

describe('Document Store', () => {
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useDocumentStore()
    vi.clearAllMocks()
  })

  afterEach(() => {
    store.stopPolling()
  })

  it('has correct initial state', () => {
    expect(store.documents).toEqual([])
    expect(store.loading).toBe(false)
    expect(store.currentDocument).toBeNull()
  })

  it('fetchDocuments loads document list', async () => {
    const mockDocs = [
      { id: '1', filename: 'file1.pdf', status: 'ready', chunk_count: 10 },
      { id: '2', filename: 'file2.docx', status: 'ready', chunk_count: 5 },
    ]
    api.get.mockResolvedValue({ data: mockDocs })

    await store.fetchDocuments()

    expect(store.documents).toEqual(mockDocs)
    expect(api.get).toHaveBeenCalledWith('/documents')
  })

  it('fetchDocuments handles error', async () => {
    api.get.mockRejectedValue(new Error('Network error'))

    await expect(store.fetchDocuments()).rejects.toThrow('Network error')
    expect(store.loading).toBe(false)
  })

  it('uploadDocument adds new document to list', async () => {
    const mockDoc = {
      id: '3',
      filename: 'upload.pdf',
      status: 'processing',
      chunk_count: 0,
      message: 'Processing',
    }
    api.post.mockResolvedValue({ data: mockDoc })

    const file = new File(['content'], 'upload.pdf', { type: 'application/pdf' })
    const result = await store.uploadDocument(file)

    expect(result).toEqual(mockDoc)
    expect(store.documents[0]).toEqual(mockDoc)
    expect(api.post).toHaveBeenCalledWith('/documents/upload', expect.any(FormData))
  })

  it('deleteDocument removes document from list', async () => {
    store.documents = [
      { id: '1', filename: 'file1.pdf' },
      { id: '2', filename: 'file2.pdf' },
    ]
    api.delete.mockResolvedValue({})

    await store.deleteDocument('1')

    expect(store.documents).toHaveLength(1)
    expect(store.documents[0].id).toBe('2')
    expect(api.delete).toHaveBeenCalledWith('/documents/1')
  })

  it('selectDocument sets currentDocument', () => {
    const doc = { id: '1', filename: 'file1.pdf' }
    store.selectDocument(doc)
    expect(store.currentDocument).toEqual(doc)
  })

  it('uploadDocument sets loading true during operation', async () => {
    let resolvePromise
    const promise = new Promise(resolve => { resolvePromise = resolve })
    api.post.mockReturnValue(promise)

    const file = new File(['content'], 'test.pdf', { type: 'application/pdf' })
    const uploadPromise = store.uploadDocument(file)

    expect(store.loading).toBe(true)
    resolvePromise({ data: { id: '1', filename: 'test.pdf' } })
    await uploadPromise
    expect(store.loading).toBe(false)
  })

  describe('readyDocuments', () => {
    it('returns only documents with status ready', () => {
      store.documents = [
        { id: '1', filename: 'ready.pdf', status: 'ready' },
        { id: '2', filename: 'pending.pdf', status: 'processing' },
        { id: '3', filename: 'ready2.pdf', status: 'ready' },
      ]
      expect(store.readyDocuments).toHaveLength(2)
      expect(store.readyDocuments.map(d => d.filename)).toEqual(['ready.pdf', 'ready2.pdf'])
    })

    it('returns empty array when no documents are ready', () => {
      store.documents = [
        { id: '1', filename: 'pending.pdf', status: 'processing' },
      ]
      expect(store.readyDocuments).toHaveLength(0)
    })
  })

  describe('hasDocuments', () => {
    it('returns true when documents exist', () => {
      store.documents = [{ id: '1', filename: 'doc.pdf', status: 'ready' }]
      expect(store.hasDocuments).toBe(true)
    })

    it('returns false when no documents', () => {
      store.documents = []
      expect(store.hasDocuments).toBe(false)
    })
  })

  describe('SWR cache', () => {
    beforeEach(() => {
      vi.useFakeTimers()
    })

    afterEach(() => {
      vi.useRealTimers()
    })

    it('returns cached data when fetched within 30s (no API call)', async () => {
      const mockDocs = [
        { id: '1', filename: 'cached.pdf', status: 'ready' },
      ]
      api.get.mockResolvedValue({ data: mockDocs })

      // First fetch
      await store.fetchDocuments()
      expect(api.get).toHaveBeenCalledTimes(1)

      // Second fetch within 30s should skip API
      await store.fetchDocuments()
      expect(api.get).toHaveBeenCalledTimes(1) // Still 1, not 2
    })

    it('refreshes from API when cache is stale (>30s)', async () => {
      const mockDocs = [
        { id: '1', filename: 'doc.pdf', status: 'ready' },
      ]
      api.get.mockResolvedValue({ data: mockDocs })

      // First fetch
      await store.fetchDocuments()
      expect(api.get).toHaveBeenCalledTimes(1)

      // Advance 35 seconds
      vi.advanceTimersByTime(35000)

      // Second fetch should call API again
      await store.fetchDocuments()
      expect(api.get).toHaveBeenCalledTimes(2)
    })

    it('forceRefresh bypasses cache', async () => {
      const mockDocs = [
        { id: '1', filename: 'doc.pdf', status: 'ready' },
      ]
      api.get.mockResolvedValue({ data: mockDocs })

      await store.fetchDocuments()
      expect(api.get).toHaveBeenCalledTimes(1)

      await store.fetchDocuments(true) // forceRefresh
      expect(api.get).toHaveBeenCalledTimes(2)
    })
  })

  describe('auto-polling for processing documents', () => {
    beforeEach(() => {
      vi.useFakeTimers()
    })

    afterEach(() => {
      store.stopPolling()
      vi.useRealTimers()
    })

    it('starts polling when upload returns processing document', async () => {
      const mockDoc = {
        id: '3',
        filename: 'upload.pdf',
        status: 'processing',
        chunk_count: 0,
      }
      api.post.mockResolvedValue({ data: mockDoc })

      const file = new File(['content'], 'upload.pdf', { type: 'application/pdf' })
      await store.uploadDocument(file)

      expect(store.isPolling).toBe(true)
      expect(store.hasProcessingDocuments).toBe(true)
    })

    it('updates document to ready and stops polling on completion', async () => {
      store.documents = [
        { id: '3', filename: 'upload.pdf', status: 'processing', chunk_count: 0 },
      ]
      store.startPolling()
      expect(store.isPolling).toBe(true)

      const readyDocs = [
        { id: '3', filename: 'upload.pdf', status: 'ready', chunk_count: 12 },
      ]
      api.get.mockResolvedValue({ data: readyDocs })

      await vi.advanceTimersByTimeAsync(2600)

      expect(store.documents[0].status).toBe('ready')
      expect(store.documents[0].chunk_count).toBe(12)
      expect(store.isPolling).toBe(false)
      expect(store.hasProcessingDocuments).toBe(false)
    })

    it('stopPolling cancels timer and sets isPolling to false', () => {
      store.documents = [
        { id: '3', filename: 'upload.pdf', status: 'processing', chunk_count: 0 },
      ]
      store.startPolling()
      expect(store.isPolling).toBe(true)

      store.stopPolling()
      expect(store.isPolling).toBe(false)
    })
  })
})
