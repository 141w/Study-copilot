import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// Mock the stores used by ChatMessage
vi.mock('@/stores/document', () => ({
  useDocumentStore: () => ({
    documents: [
      { id: 'doc1', filename: 'test.pdf' },
      { id: 'doc2', filename: 'notes.pdf' },
    ],
  }),
}))

vi.mock('@/stores/toast', () => ({
  useToastStore: () => ({
    show: vi.fn(),
    error: vi.fn(),
    success: vi.fn(),
  }),
}))

import ChatMessage from '@/components/chat/ChatMessage.vue'

describe('ChatMessage Component', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders user message with correct styling', () => {
    const wrapper = mount(ChatMessage, {
      props: {
        message: {
          id: 1,
          role: 'user',
          content: 'Hello, what is AI?',
          created_at: new Date().toISOString(),
        },
      },
    })

    // User messages should have the dark background styling
    const messageContainer = wrapper.find('.bg-\\[\\#010120\\]')
    expect(messageContainer.exists()).toBe(true)
    // Content should be rendered
    expect(wrapper.text()).toContain('Hello, what is AI?')
  })

  it('renders assistant message with sources', () => {
    const wrapper = mount(ChatMessage, {
      props: {
        message: {
          id: 2,
          role: 'assistant',
          content: 'AI is artificial intelligence.',
          sources: [
            { document_id: 'doc1', text: 'Source text here', relevance_score: 0.95 },
          ],
          created_at: new Date().toISOString(),
        },
      },
    })

    // Assistant message should render content
    expect(wrapper.text()).toContain('AI is artificial intelligence')
    // Sources section should be present
    expect(wrapper.text()).toContain('参考来源')
    expect(wrapper.text()).toContain('test.pdf')
    expect(wrapper.text()).toContain('95% 匹配')
  })

  it('shows copy button only for assistant messages', () => {
    const userWrapper = mount(ChatMessage, {
      props: {
        message: {
          id: 1,
          role: 'user',
          content: 'Hello',
          created_at: new Date().toISOString(),
        },
      },
    })

    const assistantWrapper = mount(ChatMessage, {
      props: {
        message: {
          id: 2,
          role: 'assistant',
          content: 'Hi there!',
          created_at: new Date().toISOString(),
        },
      },
    })

    // Copy button should not exist for user messages
    expect(userWrapper.text()).not.toContain('复制')
    // Copy button should exist for assistant messages
    expect(assistantWrapper.text()).toContain('复制')
  })
})
