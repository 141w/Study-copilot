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
import ElementPlus from 'element-plus'
import FavoriteStar from '@/components/FavoriteStar.vue'
import { useFavoriteStore } from '@/stores/favorite'
import api from '@/services/api'

// FavoriteStar 现在渲染 el-button circle（图标钮统一规范），
// 需在本 mount 显式装 EP 插件——tests/setup.js 里的注册挂在被丢弃的 app 实例上，
// 对 VTU 自建的 app 无效，不装则 <el-button> 只会渲染成未解析的自定义元素。
const globalOpts = { plugins: [ElementPlus] }

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
      global: { ...globalOpts, stubs: { 'el-icon': true } }
    })
    await wrapper.vm.$nextTick()
    expect(wrapper.attributes('data-active')).toBe('0')
    await wrapper.find('button').trigger('click')
    await wrapper.vm.$nextTick()
    const store = useFavoriteStore()
    expect(store.isFavorite('document', 'd1')).toBe(true)
    expect(wrapper.attributes('data-active')).toBe('1')
  })

  it('皮肤为 el-button circle 图标圆钮，且保留未收藏/已收藏双态', async () => {
    api.post.mockResolvedValue({
      data: { id: 'f2', resource_type: 'note', resource_id: 'n1' }
    })
    const wrapper = mount(FavoriteStar, {
      props: { type: 'note', id: 'n1' },
      global: { ...globalOpts, stubs: { 'el-icon': true } }
    })
    await wrapper.vm.$nextTick()
    // 真解析成原生 button，并带上 EP 的 circle 皮肤类
    expect(wrapper.element.tagName).toBe('BUTTON')
    expect(wrapper.classes()).toContain('is-circle')
    expect(wrapper.classes()).toContain('el-button')
    // 不再残留手写的 Tailwind 尺寸/圆角
    expect(wrapper.classes().join(' ')).not.toMatch(/w-7|h-7|rounded-md|rounded-lg/)
    // 选中态由 is-fav 表达，不占用 type=primary
    expect(wrapper.classes()).not.toContain('el-button--primary')
    await wrapper.find('button').trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.classes()).toContain('is-fav')
  })
})
