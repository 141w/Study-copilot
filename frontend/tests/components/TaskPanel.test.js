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

import { setActivePinia, createPinia } from 'pinia'
import TaskPanel from '@/components/TaskPanel.vue'
import api from '@/services/api'
import { useDocumentStore } from '@/stores/document'

async function mountWithTasks(tasks) {
  const store = useDocumentStore()
  store.documents = [{ id: 'd1', filename: 'a.pdf', status: 'ready' }]
  api.get.mockImplementation(url => {
    if (String(url).includes('/tasks')) return Promise.resolve({ data: { tasks } })
    return Promise.resolve({ data: [] })
  })
  const w = mount(TaskPanel, {
    global: {
      stubs: {
        'el-button': {
          template: '<button @click="$emit(\'click\')"><slot /></button>',
          emits: ['click']
        },
        'el-select': true,
        'el-option': true,
        'el-input': true,
        'el-icon': true,
        'el-dropdown': true,
        'el-dropdown-menu': true,
        'el-dropdown-item': true
      }
    }
  })
  await w.vm.$nextTick()
  await w.vm.$nextTick()
  await w.vm.$nextTick()
  return w
}

describe('TaskPanel F7 自动打标展示', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('成功时显示 N 成功与标签列表', async () => {
    const w = await mountWithTasks([
      {
        id: 't1',
        task_type: 'document_auto_tag',
        status: 'completed',
        progress: 1,
        created_at: '2026-09-29T00:00:00Z',
        completed_at: '2026-09-29T00:00:05Z',
        result: { doc_id: 'd1', picked: ['机器学习', '优化'], status: 'ok' },
        error: null
      }
    ])
    expect(w.text()).toContain('自动打标')
    expect(w.text()).toContain('2 成功')
    expect(w.text()).toContain('机器学习')
  })

  it('失败时显示失败原因而非「未匹配到合适标签」', async () => {
    const w = await mountWithTasks([
      {
        id: 't2',
        task_type: 'document_auto_tag',
        status: 'completed',
        progress: 1,
        created_at: '2026-09-29T00:00:00Z',
        completed_at: '2026-09-29T00:00:02Z',
        result: { doc_id: 'd1', picked: [], status: 'failed', error: '模型超时' },
        error: null
      }
    ])
    expect(w.text()).toContain('自动打标失败')
    expect(w.text()).toContain('模型超时')
    expect(w.text()).not.toContain('未匹配到合适标签')
  })
})
