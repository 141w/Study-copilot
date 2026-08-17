import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// Mock the stores used by UploadView
vi.mock('@/stores/document', () => ({
  useDocumentStore: () => ({
    documents: [],
    loading: false,
    fetchDocuments: vi.fn(),
    uploadDocument: vi.fn(),
    deleteDocument: vi.fn(),
  }),
}))

vi.mock('@/stores/toast', () => ({
  useToastStore: () => ({
    show: vi.fn(),
    error: vi.fn(),
    success: vi.fn(),
  }),
}))

// Mock gsap since it tries to manipulate DOM
vi.mock('gsap', () => ({
  default: {
    context: vi.fn(() => ({ revert: vi.fn() })),
    from: vi.fn(),
  },
}))

import UploadView from '@/views/UploadView.vue'

describe('UploadView Component', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders the upload page title', () => {
    const wrapper = mount(UploadView)

    expect(wrapper.find('h1').text()).toBe('上传文档')
  })

  it('shows empty state when no documents exist', () => {
    const wrapper = mount(UploadView)

    expect(wrapper.text()).toContain('暂无文档，请先上传')
  })

  it('displays file type badges', () => {
    const wrapper = mount(UploadView)

    expect(wrapper.text()).toContain('PDF')
    expect(wrapper.text()).toContain('Word')
    expect(wrapper.text()).toContain('PowerPoint')
  })

  it('has a hidden file input with correct accept attribute', () => {
    const wrapper = mount(UploadView)

    const fileInput = wrapper.find('input[type="file"]')
    expect(fileInput.exists()).toBe(true)
    expect(fileInput.attributes('accept')).toBe('.pdf,.docx,.pptx')
  })

  it('has a select file button', () => {
    const wrapper = mount(UploadView)

    const button = wrapper.find('button')
    expect(button.exists()).toBe(true)
    expect(button.text()).toBe('选择文件')
  })
})
