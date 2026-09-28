import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import DocumentPicker from '@/components/common/DocumentPicker.vue'

describe('DocumentPicker', () => {
  it('多选标签模式：点击按钮触发 update:modelValue', async () => {
    const wrapper = mount(DocumentPicker, {
      props: {
        modelValue: [],
        documents: [{ id: 'doc-1', filename: 'doc1.pdf', status: 'ready' }],
        mode: 'multiple'
      }
    })

    const btn = wrapper.find('button[role="checkbox"]')
    expect(btn.exists()).toBe(true)
    expect(btn.attributes('aria-checked')).toBe('false')

    // 点击按钮选中
    await btn.trigger('click')
    const emitted = wrapper.emitted('update:modelValue')
    expect(emitted).toBeTruthy()
    expect(emitted[0][0]).toEqual(['doc-1'])
  })

  it('多选标签模式：再次点击已选中文档触发取消选中', async () => {
    const wrapper = mount(DocumentPicker, {
      props: {
        modelValue: ['doc-1'],
        documents: [{ id: 'doc-1', filename: 'doc1.pdf', status: 'ready' }],
        mode: 'multiple'
      }
    })

    const btn = wrapper.find('button[role="checkbox"]')
    expect(btn.attributes('aria-checked')).toBe('true')

    await btn.trigger('click')
    const emitted = wrapper.emitted('update:modelValue')
    expect(emitted).toBeTruthy()
    expect(emitted[0][0]).toEqual([])
  })

  it('卡片模式：点击卡片触发 update:modelValue', async () => {
    const wrapper = mount(DocumentPicker, {
      props: {
        modelValue: [],
        documents: [{ id: 'doc-1', filename: 'doc1.pdf', status: 'ready' }],
        mode: 'cards'
      }
    })

    const card = wrapper.find('div[role="button"]')
    expect(card.exists()).toBe(true)

    await card.trigger('click')
    expect(wrapper.emitted('update:modelValue')?.[0][0]).toEqual(['doc-1'])
  })

  it('单选模式：选择 radio 触发 update:modelValue', async () => {
    const wrapper = mount(DocumentPicker, {
      props: {
        modelValue: null,
        documents: [{ id: 'doc-1', filename: 'doc1.pdf', status: 'ready' }],
        mode: 'radio'
      }
    })

    const radio = wrapper.find('input[type="radio"]')
    expect(radio.exists()).toBe(true)

    await radio.trigger('change')
    expect(wrapper.emitted('update:modelValue')?.[0][0]).toBe('doc-1')
  })

  it('空文档时渲染 emptyText 提示', () => {
    const wrapper = mount(DocumentPicker, {
      props: {
        modelValue: [],
        documents: [],
        mode: 'multiple',
        emptyText: '暂无文档'
      }
    })

    expect(wrapper.text()).toContain('暂无文档')
  })
})
