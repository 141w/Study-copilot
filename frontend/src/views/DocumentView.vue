<template>
  <div class="max-w-4xl mx-auto px-6 py-8">
    <h1 class="text-2xl font-semibold text-[var(--text-primary)] mb-8">文档阅读</h1>

    <!-- Document List -->
    <div class="mb-8">
      <h2 class="text-lg font-medium text-[var(--text-secondary)] mb-4">选择要阅读的文档</h2>
      <div v-if="documentStore.loading" class="text-center py-8 text-[var(--text-muted)]">
        加载中...
      </div>
      <div v-else-if="documentStore.documents.length === 0" class="text-center py-8 text-[var(--text-muted)]">
        暂无已上传的文档
      </div>
      <div v-else class="grid grid-cols-2 md:grid-cols-3 gap-4">
        <div
          v-for="doc in documentStore.documents"
          :key="doc.id"
          @click="selectDocument(doc)"
          @keydown.enter="selectDocument(doc)"
          role="button"
          tabindex="0"
          :aria-label="`阅读文档 ${doc.filename}`"
          class="p-4 border rounded-xl cursor-pointer transition-all bg-[var(--surface-card)] shadow-sm hover:shadow-md"
          :class="selectedDoc?.id === doc.id ? 'border-l-4 border-l-[var(--color-primary)] ring-1 ring-[var(--color-primary)]' : 'border-[var(--border-default)] hover:border-[var(--border-hover)]'"
        >
          <div class="flex items-center gap-2 mb-2">
            <svg class="w-5 h-5 text-[var(--color-error)]" fill="currentColor" viewBox="0 0 24 24">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6z"/>
              <path d="M14 2v6h6"/>
            </svg>
            <span class="text-xs px-2 py-0.5 rounded"
              :class="doc.status === 'ready' ? 'bg-[var(--color-success-light)] text-[var(--color-success)]' : 'bg-[var(--color-warning-light)] text-[var(--color-warning)]'"
            >
              {{ doc.status === 'ready' ? '已就绪' : '处理中' }}
            </span>
          </div>
          <p class="text-sm font-medium text-[var(--text-primary)] truncate">{{ doc.filename }}</p>
          <p class="text-xs text-[var(--text-muted)] mt-1">{{ formatSize(doc.file_size) }}</p>
        </div>
      </div>
    </div>

    <!-- Document Content -->
    <div v-if="selectedDoc" class="card !p-0">
      <!-- Header -->
      <div class="p-4 border-b border-[var(--border-default)] flex items-center justify-between bg-[var(--bg-secondary)] rounded-t-xl">
        <div>
          <h2 class="font-medium text-[var(--text-primary)]">{{ selectedDoc.filename }}</h2>
          <p class="text-sm text-[var(--text-muted)] mt-1">共 {{ filteredChunks.length }} 个段落</p>
        </div>
        <div class="flex items-center gap-3">
          <button
            @click="openTransform"
            class="p-2 text-[var(--text-muted)] hover:text-[var(--color-accent)] transition-colors"
            title="内容转换"
            aria-label="内容转换"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
            </svg>
          </button>
          <button
            @click="copyAllText"
            class="p-2 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
            title="复制全文"
            aria-label="复制全文"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
          </button>
        </div>
      </div>

      <!-- Search -->
      <div class="p-4 border-b border-[var(--border-default)] bg-[var(--bg-secondary)]">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="搜索文档内容..."
          class="w-full px-4 py-2.5 border border-[var(--border-default)] rounded-xl bg-[var(--bg-primary)] focus:outline-none focus:border-[var(--border-focus)] focus:ring-1 focus:ring-[var(--color-primary)] text-base"
        />
      </div>

      <!-- Content -->
      <div ref="contentRef" class="p-6 max-h-[70vh] overflow-y-auto bg-[var(--bg-secondary)]">
        <div v-if="filteredChunks.length === 0" class="text-center py-12 text-[var(--text-muted)]">
          文档内容加载中...
        </div>
        <div v-else class="space-y-4">
          <div
            v-for="chunk in paginatedChunks"
            :key="chunk.idx"
            class="group bg-[var(--surface-card)] rounded-xl shadow-sm border border-[var(--border-default)] hover:shadow-md hover:border-[var(--border-hover)] transition-all duration-200"
          >
            <!-- Chunk Header -->
            <div class="flex items-center justify-between px-4 py-3 border-b border-[var(--border-default)] bg-[var(--bg-secondary)]/50 rounded-t-xl">
              <div class="flex items-center gap-3">
                <span class="text-xs font-medium tracking-wider text-[var(--text-muted)] uppercase">
                  {{ chunk.page ? `PAGE ${chunk.page}` : `CHUNK ${filteredChunks.findIndex(c => c.idx === chunk.idx) + 1}` }}
                </span>
              </div>
              <!-- Hover Actions（P3-3：md 常显 / 触屏点按可见）-->
              <div class="flex items-center gap-1 md:opacity-0 md:group-hover:opacity-100 focus-within:opacity-100 opacity-100 transition-opacity">
                <button
                  @click="explainChunk(chunk)"
                  class="p-1.5 text-[var(--text-muted)] hover:text-[var(--color-info)] hover:bg-[var(--color-info-light)] rounded transition-colors"
                  title="解释此段"
                  aria-label="解释此段"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                  </svg>
                </button>
                <button
                  @click="generateQuiz(chunk)"
                  class="p-1.5 text-[var(--text-muted)] hover:text-[var(--color-success)] hover:bg-[var(--color-success-light)] rounded transition-colors"
                  title="基于此段出题"
                  aria-label="基于此段出题"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                  </svg>
                </button>
                <button
                  @click="copyText(chunk.text)"
                  class="p-1.5 text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] rounded transition-colors"
                  title="复制文本"
                  aria-label="复制文本"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                </button>
              </div>
            </div>

            <!-- Chunk Content（精修批次3：中文长文行高 1.75） -->
            <div class="p-4">
              <p class="text-base text-[var(--text-secondary)] leading-[1.75] whitespace-pre-wrap">{{ cleanText(chunk.text) }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Pagination（P2-5：el-pagination 替换手写按钮） -->
      <div v-if="filteredChunks.length > pageSize" class="p-4 border-t border-[var(--border-default)] bg-[var(--bg-secondary)] rounded-b-xl flex justify-center">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="filteredChunks.length"
          layout="prev, pager, next, jumper"
          background
          @current-change="scrollToContent"
        />
      </div>
    </div>

    <!-- Back to Top Button -->
    <button
      v-if="showBackToTop"
      @click="scrollToTop"
      class="fixed bottom-8 right-8 w-12 h-12 bg-[var(--color-primary)] text-white rounded-full shadow-lg flex items-center justify-center hover:opacity-90 transition-all"
      aria-label="回到顶部"
    >
      <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 10l7-7m0 0l7 7m-7-7v18" />
      </svg>
    </button>

    <!-- Transform Dialog -->
    <TransformDialog
      v-model:visible="showTransformDialog"
      :source-text="transformDocText"
      :source-title="transformDocTitle"
      :document-id="selectedDoc?.id"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useQuizStore } from '../stores/quiz'
import { useDocumentStore } from '../stores/document'
import { useToastStore } from '../stores/toast'
import { formatSize, cleanPdfText } from '../composables/useFormat'
import type { Document as DocumentModel } from '../types/models'
import TransformDialog from '../components/TransformDialog.vue'
import api from '../services/api'

/** 文档 chunk（GET /documents/:id 响应展平 + 视图序号） */
interface DocChunk {
  idx: number
  text: string
  page?: string
}

const router = useRouter()
const quizStore = useQuizStore()
// P1-4：文档列表统一走 document store（原先本地 documents 副本 + 自行 fetch，
// 与 store 数据源分裂）；提示统一走 toast store（原本地 toast 双轨）
const documentStore = useDocumentStore()
const toast = useToastStore()

const selectedDoc = ref<DocumentModel | null>(null)
const chunks = ref<DocChunk[]>([])
const searchQuery = ref('')
const currentPage = ref(1)
const pageSize = 15
const contentRef = ref<HTMLElement | null>(null)
const showBackToTop = ref(false)

// Transform dialog state
const showTransformDialog = ref(false)
const transformDocText = ref('')
const transformDocTitle = ref('')

const filteredChunks = computed<DocChunk[]>(() => {
  if (!searchQuery.value.trim()) {
    return chunks.value
  }
  const query = searchQuery.value.toLowerCase()
  return chunks.value.filter(chunk =>
    chunk.text && chunk.text.toLowerCase().includes(query)
  )
})

const paginatedChunks = computed<DocChunk[]>(() => {
  const start = (currentPage.value - 1) * pageSize
  return filteredChunks.value.slice(start, start + pageSize)
})

// P2-1：cleanText/formatSize 由 useFormat 提供（原为本地实现）
const cleanText = cleanPdfText

async function selectDocument(doc: DocumentModel): Promise<void> {
  selectedDoc.value = doc
  chunks.value = []
  searchQuery.value = ''
  currentPage.value = 1
  // 同步选中态到 store（供侧栏等处联动）
  documentStore.selectDocument(doc)

  try {
    const response = await api.get<{ chunks: DocChunk[] }>(`/documents/${doc.id}`)
    if (response.data.chunks) {
      chunks.value = response.data.chunks.map((c, i) => ({ ...c, idx: i }))
    }
  } catch (error) {
    console.error('Failed to load document:', error)
    toast.error('文档内容加载失败')
  }
}

function scrollToContent(): void {
  if (contentRef.value) {
    contentRef.value.scrollTop = 0
  }
}

function scrollToTop(): void {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function handleScroll(): void {
  showBackToTop.value = window.scrollY > 300
}

function copyText(text: string): void {
  navigator.clipboard.writeText(text)
  toast.success('已复制到剪贴板')
}

function copyAllText(): void {
  const text = chunks.value.map(c => c.text).join('\n\n')
  navigator.clipboard.writeText(text)
  toast.success('全文已复制到剪贴板')
}

function explainChunk(chunk: DocChunk): void {
  // 跳转到问答页面并带入这段文本
  router.push({
    path: '/chat',
    query: {
      context: chunk.text.substring(0, 500),
      docId: selectedDoc.value?.id
    }
  })
}

async function generateQuiz(_chunk: DocChunk): Promise<void> {
  if (!selectedDoc.value) return
  try {
    toast.info('正在生成题目...')
    await quizStore.generateQuizzes([selectedDoc.value.id], 3, 1)
    router.push('/quiz')
  } catch (_error) {
    toast.error('生成失败，请重试')
  }
}

function openTransform(): void {
  if (!selectedDoc.value) return
  // Combine all chunks as the source text
  const allText = chunks.value.map(c => c.text).join('\n\n')
  transformDocText.value = allText
  transformDocTitle.value = selectedDoc.value.filename
  showTransformDialog.value = true
}

onMounted(() => {
  documentStore.fetchDocuments()
  window.addEventListener('scroll', handleScroll)
})

onUnmounted(() => {
  window.removeEventListener('scroll', handleScroll)
})
</script>
