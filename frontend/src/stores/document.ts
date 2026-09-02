import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import api from '../services/api'
import type { Document } from '../types/models'

export const useDocumentStore = defineStore('document', () => {
  const documents = ref<Document[]>([])
  const loading = ref(false)
  const currentDocument = ref<Document | null>(null)
  const lastFetched = ref(0)

  const readyDocuments = computed(() =>
    documents.value.filter(d => d.status === 'ready')
  )

  const hasDocuments = computed(() => documents.value.length > 0)

  /** Return cached data if fetched within the last 30 seconds. */
  function isCacheFresh(): boolean {
    return Date.now() - lastFetched.value < 30_000
  }

  async function fetchDocuments(forceRefresh = false): Promise<void> {
    if (!forceRefresh && isCacheFresh() && documents.value.length > 0) {
      return // Stale-while-revalidate: return cached
    }
    loading.value = true
    try {
      const response = await api.get<Document[]>('/documents')
      documents.value = response.data
      lastFetched.value = Date.now()
    } catch (error) {
      console.error('Error fetching documents:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function uploadDocument(file: File): Promise<Pick<Document, 'id' | 'filename' | 'status' | 'chunk_count'> & { message?: string }> {
    loading.value = true
    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await api.post<Document>('/documents/upload', formData)

      documents.value.unshift(response.data)
      return response.data
    } catch (error) {
      console.error('Error uploading document:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function deleteDocument(documentId: string): Promise<void> {
    try {
      await api.delete(`/documents/${documentId}`)
      documents.value = documents.value.filter(d => d.id !== documentId)
    } catch (error) {
      console.error('Error deleting document:', error)
      throw error
    }
  }

  function selectDocument(doc: Document | null): void {
    currentDocument.value = doc
  }

  return {
    documents,
    loading,
    currentDocument,
    lastFetched,
    readyDocuments,
    hasDocuments,
    fetchDocuments,
    uploadDocument,
    deleteDocument,
    selectDocument
  }
})
