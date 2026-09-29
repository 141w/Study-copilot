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

/**
 * F1 · 概念页双链渲染产物断言（fix(phase2-audit): F1）
 *
 * 原测试（本文件上方 5.1 用例）只断言侧栏死链文案 `w.text()` 含 `[[missing]]`，
 * 从未检查 `.wiki-body` 的 v-html 渲染产物，因此 `html:false` 把占位符转义成
 * 字面文本时仍然全绿——这正是漏检原因。本组断言产物 HTML 本身。
 */
describe('WikiView F1 双链渲染产物', () => {
  beforeEach(() => vi.clearAllMocks())

  async function mountWithContent(content, resolveMap = {}) {
    api.get.mockImplementation(url => {
      if (url === '/wiki') return Promise.resolve({ data: list })
      if (url === '/wiki/p1') {
        return Promise.resolve({
          data: { ...page, content, links: Object.keys(resolveMap), dead_links: [] }
        })
      }
      if (url === '/wiki/resolve') return Promise.resolve({ data: resolveMap })
      return Promise.resolve({ data: [] })
    })
    const w = mountView()
    await w.vm.$nextTick()
    await w.vm.$nextTick()
    await w.find('[data-test="wiki-item-gd"]').trigger('click')
    await w.vm.$nextTick()
    await w.vm.$nextTick()
    return w
  }

  it('[[slug]] 渲染为可点 <a data-slug>，且不残留占位符/转义实体', async () => {
    const w = await mountWithContent('前句 [[梯度下降]] 后句仍在。', {
      '梯度下降': { id: 'p-gd', title: '梯度下降' }
    })
    const body = w.find('.wiki-body')
    expect(body.exists()).toBe(true)
    const html = body.html()

    // 产物中必须有真正的锚点
    expect(html).toMatch(/<a[^>]*data-slug="[^"]*梯度下降[^"]*"[^>]*>梯度下降<\/a>/)
    // 不得残留 HTML 占位符字面量或被转义的标签
    expect(html).not.toContain('wl-placeholder')
    expect(html).not.toContain('&lt;')
    expect(html).not.toContain('＜')
  })

  it('行内双链不得把句子切成多个段落', async () => {
    const w = await mountWithContent('前句 [[梯度下降]] 后句仍在。', {
      '梯度下降': { id: 'p-gd', title: '梯度下降' }
    })
    const body = w.find('.wiki-body')
    const ps = body.element.querySelectorAll('p')
    // 同一句必须在同一个 <p> 内
    expect(ps.length).toBe(1)
    expect(ps[0].textContent).toContain('前句')
    expect(ps[0].textContent).toContain('梯度下降')
    expect(ps[0].textContent).toContain('后句仍在')
  })

  it('活链带 wiki-link-ok，死链带 wiki-link-dead 与创建提示 title', async () => {
    const w = await mountWithContent('用 [[梯度下降]] 和 [[不存在的概念]] 做对比。', {
      '梯度下降': { id: 'p-gd', title: '梯度下降' },
      '不存在的概念': null
    })
    const body = w.find('.wiki-body')
    const ok = body.element.querySelector('a.wiki-link-ok, a[data-slug="梯度下降"]')
    const dead = body.element.querySelector('a.wiki-link-dead')
    expect(ok).toBeTruthy()
    expect(dead).toBeTruthy()
    // 死链需要可见的创建提示
    const deadTitle = dead.getAttribute('title') || dead.getAttribute('data-tooltip') || ''
    expect(deadTitle).toContain('尚未创建')
  })

  it('[[slug|label]] 自定义链接文本', async () => {
    const w = await mountWithContent('见 [[梯度下降|GD 算法]] 的细节。', {
      '梯度下降': { id: 'p-gd', title: '梯度下降' }
    })
    const html = w.find('.wiki-body').html()
    expect(html).toMatch(/<a[^>]*>GD 算法<\/a>/)
    expect(html).not.toContain('wl-placeholder')
  })
})

describe('WikiView 5.3 死链巡检', () => {
  beforeEach(() => vi.clearAllMocks())

  it('巡检展示死链与孤页', async () => {
    api.get.mockImplementation(url => {
      if (url === '/wiki') return Promise.resolve({ data: list })
      if (url === '/wiki/audit/dead-links') {
        return Promise.resolve({
          data: {
            stats: { pages: 2, links: 3, dead_links: 1, orphan_pages: 1 },
            pages: [{ id: 'p1', slug: 'gd', title: '梯度下降', dead_links: ['ghost'] }],
            orphan_pages: [{ id: 'p2', slug: 'x', title: '孤页' }]
          }
        })
      }
      return Promise.resolve({ data: [] })
    })
    const w = mountView()
    await w.vm.$nextTick()
    await w.vm.$nextTick()
    await w.find('[data-test="wiki-audit"]').trigger('click')
    await w.vm.$nextTick()
    await w.vm.$nextTick()
    expect(w.find('[data-test="wiki-audit-report"]').exists()).toBe(true)
    expect(w.find('[data-test="audit-dead-count"]').text()).toContain('1')
    expect(w.text()).toContain('[[ghost]]')
    expect(w.text()).toContain('孤页')
  })
})
