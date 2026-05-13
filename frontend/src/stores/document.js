import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../services/api'

export const useDocumentStore = defineStore('document', () => {
  const documents = ref([])
  const loading = ref(false)
  const currentDocument = ref(null)
  
  async function fetchDocuments() {
    loading.value = true
    try {
      const response = await api.get('/documents')
      documents.value = response.data
    } catch (error) {
      console.error('Error fetching documents:', error)
    } finally {
      loading.value = false
    }
  }
  
  async function uploadDocument(file) {
    loading.value = true
    try {
      const formData = new FormData()
      formData.append('file', file)
      
       const response = await api.post('/documents/upload', formData)
      
      documents.value.unshift(response.data)
      return response.data
    } catch (error) {
      console.error('Error uploading document:', error)
      throw error
    } finally {
      loading.value = false
    }
  }
  
  async function deleteDocument(documentId) {
    try {
      await api.delete(`/documents/${documentId}`)
      documents.value = documents.value.filter(d => d.id !== documentId)
    } catch (error) {
      console.error('Error deleting document:', error)
      throw error
    }
  }
  
  function selectDocument(doc) {
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