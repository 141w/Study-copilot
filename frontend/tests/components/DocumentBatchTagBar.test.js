import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('@/services/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
  cancelAll: vi.fn(),
}))
vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))

import DocumentBatchTagBar from '@/components/DocumentBatchTagBar.vue'
import api from '@/services/api'

describe('DocumentBatchTagBar（阶段二）', () => {
  beforeEach(() => vi.clearAllMocks())

  function mountBar(selected = ['d1', 'd2'], selectMode = true) {
    return mount(DocumentBatchTagBar, {
      props: { selected, selectMode },
      global: {
        stubs: {
          'el-button': {
            template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
            props: ['disabled', 'loading', 'text'],
            emits: ['click']
          },
          'el-dialog': { template: '<div><slot /><slot name="footer" /></div>', props: ['modelValue', 'title', 'width'] },
          'el-input': { template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />', props: ['modelValue', 'placeholder'] }
        }
      }
    })
  }

  it('批量模式显示打标签与自动打标', () => {
    const w = mountBar()
    expect(w.text()).toContain('已选 2')
    expect(w.text()).toContain('打标签')
    expect(w.text()).toContain('自动打标')
  })

  it('自动打标调用 batch-auto-tag', async () => {
    api.post.mockResolvedValue({ data: { results: { d1: ['A'], d2: [] } } })
    const w = mountBar()
    const btns = w.findAll('button')
    const auto = btns.find(b => b.text().includes('自动打标'))
    await auto.trigger('click')
    await w.vm.$nextTick()
    expect(api.post).toHaveBeenCalledWith('/documents/batch-auto-tag', {
      document_ids: ['d1', 'd2'],
      tag_names: []
    })
  })

  it('非批量模式只显示入口', () => {
    const w = mountBar([], false)
    expect(w.text()).toContain('批量')
    expect(w.text()).not.toContain('自动打标')
  })
})
