import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
  cancelAll: vi.fn(),
}))
vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn() },
}))

import { setActivePinia, createPinia } from 'pinia'
import RetrievalSettings from '@/components/settings/RetrievalSettings.vue'
import api from '@/services/api'

describe('RetrievalSettings（阶段一）', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('加载并回显服务端参数', async () => {
    api.get.mockResolvedValue({
      data: { embedding_top_k: 12, rrf_k: 80, rrf_vector_weight: 0.7, rrf_keyword_weight: 0.3 }
    })
    const wrapper = mount(RetrievalSettings, {
      global: { stubs: { 'el-slider': true, 'el-button': true } }
    })
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()
    expect(api.get).toHaveBeenCalledWith('/config/retrieval')
    expect(wrapper.find('[data-test="ret-val-embedding_top_k"]').text()).toBe('12')
    expect(wrapper.find('[data-test="ret-val-rrf_k"]').text()).toBe('80')
  })

  it('保存时 PUT 当前表单', async () => {
    api.get.mockResolvedValue({ data: {} })
    api.put.mockResolvedValue({ data: { embedding_top_k: 5 } })
    const wrapper = mount(RetrievalSettings, {
      global: { stubs: { 'el-slider': true, 'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>', emits: ['click'] } } }
    })
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()
    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('保存'))
    await saveBtn.trigger('click')
    await wrapper.vm.$nextTick()
    expect(api.put).toHaveBeenCalledWith('/config/retrieval', expect.objectContaining({ embedding_top_k: 5 }))
  })
})
