import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../services/api'

export interface MemoryItem {
  id: string
  kind: 'profile' | 'preference' | 'fact' | 'task' | 'interest'
  origin: 'explicit' | 'extracted' | 'manual'
  status: 'active' | 'superseded' | 'archived' | 'pending'
  key: string
  content: string
  created_at?: string | null
  updated_at?: string | null
  superseded_at?: string | null
}

export interface MemoryConfig {
  enabled: boolean
  capacity: number
  has_resident_block: boolean
  last_extracted_at: string | null
}

export const useMemoryStore = defineStore('memory', () => {
  const items = ref<MemoryItem[]>([])
  const config = ref<MemoryConfig>({
    enabled: true,
    capacity: 200,
    has_resident_block: false,
    last_extracted_at: null,
  })
  const loading = ref(false)

  const activeItems = computed(() => items.value.filter(i => i.status === 'active'))
  const pendingItems = computed(() => items.value.filter(i => i.status === 'pending'))
  const residentItems = computed(() =>
    activeItems.value.filter(i => i.kind === 'profile' || i.kind === 'preference')
  )
  const situationalItems = computed(() =>
    activeItems.value.filter(i => i.kind === 'fact' || i.kind === 'task')
  )
  const interestItems = computed(() => activeItems.value.filter(i => i.kind === 'interest'))

  async function fetchMemories() {
    loading.value = true
    try {
      const resp = await api.get('/memory')
      items.value = resp.data.items || []
      config.value = resp.data.config || config.value
    } catch (err) {
      console.error('Failed to fetch memories:', err)
    } finally {
      loading.value = false
    }
  }

  async function createMemory(payload: { kind: string; content: string; key?: string }) {
    const resp = await api.post('/memory', payload)
    await fetchMemories()
    return resp.data
  }

  async function confirmMemory(id: string) {
    const resp = await api.post(`/memory/${id}/confirm`)
    await fetchMemories()
    return resp.data
  }

  async function supersedeMemory(id: string) {
    const resp = await api.post(`/memory/${id}/supersede`)
    await fetchMemories()
    return resp.data
  }

  async function deleteMemory(id: string) {
    const resp = await api.delete(`/memory/${id}`)
    items.value = items.value.filter(i => i.id !== id)
    return resp.data
  }

  async function updateConfig(payload: { enabled?: boolean; capacity?: number }) {
    const resp = await api.put('/memory/config', payload)
    if (payload.enabled !== undefined) config.value.enabled = payload.enabled
    if (payload.capacity !== undefined) config.value.capacity = payload.capacity
    return resp.data
  }

  return {
    items,
    config,
    loading,
    activeItems,
    pendingItems,
    residentItems,
    situationalItems,
    interestItems,
    fetchMemories,
    createMemory,
    confirmMemory,
    supersedeMemory,
    deleteMemory,
    updateConfig,
  }
})
