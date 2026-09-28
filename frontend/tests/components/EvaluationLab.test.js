import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('@/services/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
  cancelAll: vi.fn(),
}))
vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))

import { setActivePinia, createPinia } from 'pinia'
import EvaluationLab from '@/components/settings/EvaluationLab.vue'
import { useDocumentStore } from '@/stores/document'
import api from '@/services/api'

describe('EvaluationLab（阶段四）', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('运行评测展示 hit 指标', async () => {
    const store = useDocumentStore()
    store.documents = [{ id: 'd1', filename: 'a.pdf', status: 'ready' }]
    api.get.mockResolvedValue({ data: [{ id: 'd1', filename: 'a.pdf', status: 'ready' }] })
    api.post.mockResolvedValue({
      data: {
        meta: { n_questions: 1, 'hit_rate@1': 1, 'hit_rate@5': 1 },
        results: [
          { question: '什么是梯度？', 'hit@1': true, top: [{ document_id: 'd1', chunk_id: 'c', score: 0.9, preview: '梯度是…' }] }
        ]
      }
    })

    const w = mount(EvaluationLab, {
      global: {
        stubs: {
          'el-button': {
            template: '<button @click="$emit(\'click\')"><slot /></button>',
            emits: ['click']
          },
          'el-select': true,
          'el-option': true,
          'el-input': {
            template: '<textarea :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)"></textarea>',
            props: ['modelValue', 'type', 'rows', 'placeholder']
          }
        }
      }
    })
    await w.vm.$nextTick()
    await w.vm.$nextTick()

    w.vm.selectedDocs = ['d1']
    w.vm.questionText = '什么是梯度？'
    await w.vm.$nextTick()
    await w.find('[data-test="eval-run"]').trigger('click')
    await w.vm.$nextTick()
    await w.vm.$nextTick()

    expect(api.post).toHaveBeenCalledWith('/evaluation/run', {
      document_ids: ['d1'],
      questions: ['什么是梯度？'],
      top_k: 5
    })
    expect(w.find('[data-test="eval-hit1"]').text()).toContain('100%')
    expect(w.text()).toContain('什么是梯度？')
  })
})
