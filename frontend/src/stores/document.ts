import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import api from '../services/api'
import type { Document } from '../types/models'
import { useToastStore } from './toast'

export const useDocumentStore = defineStore('document', () => {
  const documents = ref<Document[]>([])
  const loading = ref(false)
  const currentDocument = ref<Document | null>(null)
  const lastFetched = ref(0)
  const isPolling = ref(false)

  let pollTimer: ReturnType<typeof setTimeout> | null = null
  let pollCount = 0
  const MAX_POLLS = 60 // 60 * 2.5s = 150s 最大轮询时间

  const readyDocuments = computed(() =>
    documents.value.filter(d => d.status === 'ready')
  )

  const hasDocuments = computed(() => documents.value.length > 0)

  const hasProcessingDocuments = computed(() =>
    documents.value.some(d => d.status === 'processing')
  )

  /** Return cached data if fetched within the last 30 seconds. */
  function isCacheFresh(): boolean {
    return Date.now() - lastFetched.value < 30_000
  }

  function stopPolling(): void {
    if (pollTimer) {
      clearTimeout(pollTimer)
      pollTimer = null
    }
    isPolling.value = false
    pollCount = 0
  }

  function startPolling(): void {
    if (pollTimer) return
    if (!hasProcessingDocuments.value) return
    isPolling.value = true
    pollCount = 0
    pollTimer = setTimeout(poll, 2500)
  }

  async function poll(): Promise<void> {
    pollTimer = null
    if (!hasProcessingDocuments.value || pollCount >= MAX_POLLS) {
      stopPolling()
      return
    }

    pollCount++
    try {
      // 静默拉取：不切换 loading.value，避免页面闪烁骨架屏
      const response = await api.get<Document[]>('/documents')
      const newDocs = Array.isArray(response.data) ? response.data : []

      // 对比状态流转：从 processing 变为 ready 或 error 时触发全局提示
      try {
        const toastStore = useToastStore()
        for (const oldDoc of documents.value) {
          if (oldDoc.status === 'processing') {
            const updated = newDocs.find(d => d.id === oldDoc.id)
            if (updated) {
              if (updated.status === 'ready') {
                toastStore.success(`《${updated.filename}》解析切片完成，共生成 ${updated.chunk_count} 个知识块！`)
              } else if (updated.status === 'error') {
                toastStore.error(`《${updated.filename}》处理失败，请重试`)
              }
            }
          }
        }
      } catch (_toastErr) {
        // 环境兼容防护
      }

      documents.value = newDocs
      lastFetched.value = Date.now()
    } catch (error) {
      console.error('Error polling documents:', error)
    }

    if (hasProcessingDocuments.value && pollCount < MAX_POLLS) {
      pollTimer = setTimeout(poll, 2500)
    } else {
      stopPolling()
    }
  }

  async function fetchDocuments(forceRefresh = false): Promise<void> {
    if (!forceRefresh && isCacheFresh() && documents.value.length > 0) {
      return // Stale-while-revalidate: return cached
    }
    loading.value = true
    try {
      const response = await api.get<Document[]>('/documents')
      documents.value = Array.isArray(response.data) ? response.data : []
      lastFetched.value = Date.now()
      if (hasProcessingDocuments.value) {
        startPolling()
      }
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

      const existingIndex = documents.value.findIndex(d => d.id === response.data.id)
      if (existingIndex >= 0) {
        documents.value[existingIndex] = response.data
      } else {
        documents.value.unshift(response.data)
      }
      lastFetched.value = Date.now()

      if (response.data.status === 'processing') {
        startPolling()
      }

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
      if (!hasProcessingDocuments.value) {
        stopPolling()
      }
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
    isPolling,
    readyDocuments,
    hasDocuments,
    hasProcessingDocuments,
    fetchDocuments,
    uploadDocument,
    deleteDocument,
    selectDocument,
    startPolling,
    stopPolling,
    poll
  }
})
