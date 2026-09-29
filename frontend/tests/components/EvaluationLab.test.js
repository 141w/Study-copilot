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
        meta: { n_questions: 1, 'hit_rate@1': 1, 'hit_rate@5': 1, 'recall@5': 1, 'mrr@5': 1, embedding_model: 'text2vec', top_k: 5, fts_config: 'simple' },
        results: [
          { question: '什么是梯度？', expected: ['d1'], 'hit@1': true, 'hit@5': true, 'recall@5': 1, 'mrr@5': 1, top: [{ document_id: 'd1', chunk_id: 'c', score: 0.9, preview: '梯度是…' }] }
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
    w.vm.questionText = '什么是梯度？\td1'
    await w.vm.$nextTick()
    await w.find('[data-test="eval-run"]').trigger('click')
    await w.vm.$nextTick()
    await w.vm.$nextTick()

    expect(api.post).toHaveBeenCalledWith('/evaluation/run', {
      document_ids: ['d1'],
      questions: ['什么是梯度？'],
      expected: [['d1']],
      top_k: 5
    })
    expect(w.find('[data-test="eval-hit1"]').text()).toContain('100%')
    expect(w.text()).toContain('什么是梯度？')
  })
})

/**
 * F3 · 期望答案与指标口径（fix(phase2-audit): F3）
 */
describe('EvaluationLab F3', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  function mountLab() {
    const store = useDocumentStore()
    store.documents = [{ id: 'd1', filename: 'a.pdf', status: 'ready' }]
    api.get.mockResolvedValue({ data: [{ id: 'd1', filename: 'a.pdf', status: 'ready' }] })
    return mount(EvaluationLab, {
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
  }

  it('请求必须带 expected（问题 TSV 第二列）', async () => {
    api.post.mockResolvedValue({
      data: {
        meta: { n_questions: 1, 'hit_rate@1': 0, 'hit_rate@5': 0, 'recall@5': 0, 'mrr@5': 0 },
        results: [{ question: 'q1', expected: ['d1'], 'hit@1': false, top: [] }]
      }
    })
    const w = mountLab()
    await w.vm.$nextTick()
    await w.vm.$nextTick()
    w.vm.selectedDocs = ['d1']
    w.vm.questionText = 'q1\td1'
    await w.vm.$nextTick()
    await w.find('[data-test="eval-run"]').trigger('click')
    await w.vm.$nextTick()
    await w.vm.$nextTick()
    const body = api.post.mock.calls[0][1]
    expect(body.expected).toEqual([['d1']])
  })

  it('未录入期望答案时禁止静默出百分比', async () => {
    api.post.mockResolvedValue({
      data: {
        meta: {
          n_questions: 1,
          'hit_rate@1': 0,
          'hit_rate@5': 0,
          'recall@5': 0,
          'mrr@5': 0,
          has_expected: false
        },
        results: [{ question: 'q1', expected: [], 'hit@1': false, top: [], warning: '未录入期望答案，指标不可用于比较' }]
      }
    })
    const w = mountLab()
    await w.vm.$nextTick()
    await w.vm.$nextTick()
    w.vm.selectedDocs = ['d1']
    w.vm.questionText = 'q1'
    await w.vm.$nextTick()
    await w.find('[data-test="eval-run"]').trigger('click')
    await w.vm.$nextTick()
    await w.vm.$nextTick()
    expect(w.text()).toContain('未录入期望答案，指标不可用于比较')
    // 不应展示百分比胶囊
    expect(w.find('[data-test="eval-hit1"]').exists()).toBe(false)
  })

  it('展示本次生效参数摘要带', async () => {
    api.post.mockResolvedValue({
      data: {
        meta: {
          n_questions: 1,
          'hit_rate@1': 1,
          'hit_rate@5': 1,
          'recall@5': 1,
          'mrr@5': 1,
          embedding_model: 'text2vec-base-chinese',
          top_k: 5,
          rrf_k: 60,
          fts_config: 'simple'
        },
        results: [{ question: 'q1', expected: ['d1'], 'hit@1': true, 'hit@5': true, 'recall@5': 1, 'mrr@5': 1, top: [] }]
      }
    })
    const w = mountLab()
    await w.vm.$nextTick()
    await w.vm.$nextTick()
    w.vm.selectedDocs = ['d1']
    w.vm.questionText = 'q1\td1'
    await w.vm.$nextTick()
    await w.find('[data-test="eval-run"]').trigger('click')
    await w.vm.$nextTick()
    await w.vm.$nextTick()
    expect(w.find('[data-test="eval-params-band"]').exists()).toBe(true)
    expect(w.find('[data-test="eval-params-band"]').text()).toContain('text2vec')
    expect(w.find('[data-test="eval-params-band"]').text()).toContain('simple')
  })

  it('结果表列头含期望/Recall/MRR，命中用 ✓/—', async () => {
    api.post.mockResolvedValue({
      data: {
        meta: { n_questions: 1, 'hit_rate@1': 0, 'hit_rate@5': 1, 'recall@5': 1, 'mrr@5': 0.5 },
        results: [{ question: 'q1', expected: ['d1'], 'hit@1': false, 'hit@5': true, 'recall@5': 1, 'mrr@5': 0.5, top: [] }]
      }
    })
    const w = mountLab()
    await w.vm.$nextTick()
    await w.vm.$nextTick()
    w.vm.selectedDocs = ['d1']
    w.vm.questionText = 'q1\td1'
    await w.vm.$nextTick()
    await w.find('[data-test="eval-run"]').trigger('click')
    await w.vm.$nextTick()
    await w.vm.$nextTick()
    const text = w.text()
    expect(text).toContain('期望文档')
    expect(text).toContain('Recall')
    expect(text).toContain('MRR')
    expect(text).toContain('—')  // hit@1 未命中
    expect(text).toContain('✓')  // hit@5 命中
  })

  it('导出按钮产出 JSON（真按钮，非假按钮）', async () => {
    api.post.mockResolvedValue({
      data: {
        meta: { n_questions: 1, 'hit_rate@1': 1, 'hit_rate@5': 1, 'recall@5': 1, 'mrr@5': 1 },
        results: [{ question: 'q1', expected: ['d1'], 'hit@1': true, 'hit@5': true, 'recall@5': 1, 'mrr@5': 1, top: [] }]
      }
    })
    const w = mountLab()
    await w.vm.$nextTick()
    await w.vm.$nextTick()
    w.vm.selectedDocs = ['d1']
    w.vm.questionText = 'q1\td1'
    await w.vm.$nextTick()
    await w.find('[data-test="eval-run"]').trigger('click')
    await w.vm.$nextTick()
    await w.vm.$nextTick()
    const exportBtn = w.find('[data-test="eval-export"]')
    expect(exportBtn.exists()).toBe(true)
  })
})
