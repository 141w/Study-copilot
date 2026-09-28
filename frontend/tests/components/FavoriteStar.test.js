import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn().mockResolvedValue({ data: [] }),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
  cancelAll: vi.fn(),
}))

import { setActivePinia, createPinia } from 'pinia'
import FavoriteStar from '@/components/FavoriteStar.vue'
import { useFavoriteStore } from '@/stores/favorite'
import api from '@/services/api'

describe('FavoriteStar', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    api.get.mockResolvedValue({ data: [] })
  })

  it('未收藏时点击切换为已收藏', async () => {
    api.post.mockResolvedValue({
      data: { id: 'f1', resource_type: 'document', resource_id: 'd1' }
    })
    const wrapper = mount(FavoriteStar, {
      props: { type: 'document', id: 'd1' },
      global: { stubs: { 'el-icon': true } }
    })
    await wrapper.vm.$nextTick()
    expect(wrapper.attributes('data-active')).toBe('0')
    await wrapper.find('button').trigger('click')
    await wrapper.vm.$nextTick()
    const store = useFavoriteStore()
    expect(store.isFavorite('document', 'd1')).toBe(true)
    expect(wrapper.attributes('data-active')).toBe('1')
  })
})
