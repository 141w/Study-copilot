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
})
