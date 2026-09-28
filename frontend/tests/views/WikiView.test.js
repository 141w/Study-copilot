import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('@/services/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
  cancelAll: vi.fn(),
}))
vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
  ElMessageBox: { confirm: vi.fn().mockResolvedValue(true) },
}))

import WikiView from '@/views/WikiView.vue'
import api from '@/services/api'

const list = [{ id: 'p1', slug: 'gd', title: '梯度下降', summary: '优化' }]
const page = {
  id: 'p1',
  slug: 'gd',
  title: '梯度下降',
  summary: '优化',
  content: '见 [[missing]] 与 [[gd]]',
  revision: 1,
  links: ['missing', 'gd'],
  dead_links: ['missing']
}

function mountView() {
  return mount(WikiView, {
    global: {
      stubs: {
        'el-button': {
          template: '<button @click="$emit(\'click\')"><slot /></button>',
          emits: ['click']
        },
        'el-input': {
          template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
          props: ['modelValue', 'placeholder', 'type', 'rows', 'clearable']
        }
      }
    }
  })
}

describe('WikiView 5.1', () => {
  beforeEach(() => vi.clearAllMocks())

  it('渲染列表并打开详情，显示死链', async () => {
    api.get.mockImplementation(url => {
      if (url === '/wiki') return Promise.resolve({ data: list })
      if (url === '/wiki/p1') return Promise.resolve({ data: page })
      if (url === '/wiki/resolve') {
        return Promise.resolve({ data: { missing: null, gd: { title: '梯度下降' } } })
      }
      return Promise.resolve({ data: [] })
    })
    const w = mountView()
    await w.vm.$nextTick()
    await w.vm.$nextTick()
    expect(w.find('[data-test="wiki-item-gd"]').exists()).toBe(true)
    await w.find('[data-test="wiki-item-gd"]').trigger('click')
    await w.vm.$nextTick()
    await w.vm.$nextTick()
    expect(w.text()).toContain('梯度下降')
    expect(w.text()).toContain('死链')
    expect(w.text()).toContain('[[missing]]')
  })

  it('新建表单可填写 slug 与正文', async () => {
    api.get.mockResolvedValue({ data: [] })
    const w = mountView()
    await w.vm.$nextTick()
    await w.find('[data-test="wiki-new"]').trigger('click')
    await w.vm.$nextTick()
    expect(w.find('[data-test="wiki-editor"]').exists()).toBe(true)
    expect(w.find('[data-test="wiki-save"]').exists()).toBe(true)
  })
})
