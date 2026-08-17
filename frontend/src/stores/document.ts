import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../services/api'
import type { Document } from '../types/models'

export const useDocumentStore = defineStore('document', () => {
  const documents = ref<Document[]>([])
  const loading = ref(false)
  const currentDocument = ref<Document | null>(null)

  async function fetchDocuments(): Promise<void> {
    loading.value = true
    try {
      const response = await api.get<Document[]>('/documents')
      documents.value = response.data
    } catch (error) {
      console.error('Error fetching documents:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function uploadDocument(file: File): Promise<Document> {
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

  function selectDocument(doc: Document): void {
    currentDocument.value = doc
  }

  return {
    documents,
    loading,
    currentDocument,
    fetchDocuments,
    uploadDocument,
    deleteDocument,
    selectDocument
  }
})
