import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../services/api'

export type FavoriteType = 'document' | 'note' | 'message'

export interface FavoriteItem {
  id: string
  resource_type: FavoriteType
  resource_id: string
  created_at?: string | null
}

/** P0-B 收藏/书签 */
export const useFavoriteStore = defineStore('favorites', () => {
  const items = ref<FavoriteItem[]>([])
  const loading = ref(false)
  const loaded = ref(false)

  function isFavorite(type: FavoriteType, id: string): boolean {
    return items.value.some(f => f.resource_type === type && f.resource_id === id)
  }

  async function fetchFavorites(force = false): Promise<void> {
    if (loaded.value && !force) return
    loading.value = true
    try {
      const { data } = await api.get<FavoriteItem[]>('/favorites')
      items.value = Array.isArray(data) ? data : []
      loaded.value = true
    } catch {
      items.value = []
    } finally {
      loading.value = false
    }
  }

  async function toggle(type: FavoriteType, id: string): Promise<boolean> {
    const on = isFavorite(type, id)
    try {
      if (on) {
        await api.delete('/favorites', { params: { resource_type: type, resource_id: id } })
        items.value = items.value.filter(
          f => !(f.resource_type === type && f.resource_id === id)
        )
        return false
      }
      const { data } = await api.post<FavoriteItem>('/favorites', {
        resource_type: type,
        resource_id: id
      })
      items.value = [data, ...items.value]
      return true
    } catch {
      return on
    }
  }

  return { items, loading, loaded, isFavorite, fetchFavorites, toggle }
})
