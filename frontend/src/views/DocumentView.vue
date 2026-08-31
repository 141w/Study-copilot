<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <h1 class="text-2xl font-semibold text-[var(--text-primary)] mb-8">文档阅读</h1>

    <!-- Document List -->
    <div class="mb-8">
      <h2 class="text-lg font-medium text-[var(--text-secondary)] mb-4">选择要阅读的文档</h2>
      <div v-if="loading" class="text-center py-8 text-[var(--text-muted)]">
        加载中...
      </div>
      <div v-else-if="documents.length === 0" class="text-center py-8 text-[var(--text-muted)]">
        暂无已上传的文档
      </div>
      <div v-else class="grid grid-cols-2 md:grid-cols-3 gap-4">
        <div
          v-for="doc in documents"
          :key="doc.id"
          @click="selectDocument(doc)"
          class="p-4 border rounded-lg cursor-pointer transition-all bg-[var(--surface-card)] shadow-sm hover:shadow-md"
          :class="selectedDoc?.id === doc.id ? 'border-l-4 border-l-[var(--color-primary)] ring-1 ring-[var(--color-primary)]' : 'border-[var(--border-default)] hover:border-[var(--border-hover)]'"
        >
          <div class="flex items-center gap-2 mb-2">
            <svg class="w-5 h-5 text-red-500" fill="currentColor" viewBox="0 0 24 24">
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
    <div v-if="selectedDoc" class="el-card !p-0">
      <!-- Header -->
      <div class="p-4 border-b border-[var(--border-default)] flex items-center justify-between bg-[var(--bg-secondary)] rounded-t-lg">
        <div>
          <h2 class="font-medium text-[var(--text-primary)]">{{ selectedDoc.filename }}</h2>
          <p class="text-sm text-[var(--text-muted)] mt-1">共 {{ filteredChunks.length }} 个段落</p>
        </div>
        <div class="flex items-center gap-3">
          <button
            @click="openTransform"
            class="p-2 text-[var(--text-muted)] hover:text-purple-600 transition-colors"
            title="内容转换"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
            </svg>
          </button>
          <button
            @click="copyAllText"
            class="p-2 text-[var(--text-muted)] hover:text-[#010120] transition-colors"
            title="复制全文"
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
          class="w-full px-4 py-2.5 border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] focus:outline-none focus:border-[var(--border-focus)] focus:ring-1 focus:ring-[var(--color-primary)] text-base"
        />
      </div>
      
      <!-- Content -->
      <div ref="contentRef" class="p-6 max-h-[70vh] overflow-y-auto bg-[var(--bg-secondary)]">
        <div v-if="filteredChunks.length === 0" class="text-center py-12 text-[var(--text-muted)]">
          文档内容加载中...
        </div>
        <div v-else class="space-y-4">
          <div
            v-for="(chunk, idx) in paginatedChunks"
            :key="chunk.idx"
            class="group bg-[var(--surface-card)] rounded-lg shadow-sm border border-[var(--border-default)] hover:shadow-md hover:border-[var(--border-hover)] transition-all duration-200"
          >
            <!-- Chunk Header -->
            <div class="flex items-center justify-between px-4 py-3 border-b border-[var(--border-default)] bg-[var(--bg-secondary)]/50 rounded-t-lg">
              <div class="flex items-center gap-3">
                <span class="text-xs font-medium tracking-wider text-[var(--text-muted)] uppercase">
                  {{ chunk.page ? `PAGE ${chunk.page}` : `CHUNK ${filteredChunks.findIndex(c => c.idx === chunk.idx) + 1}` }}
                </span>
              </div>
              <!-- Hover Actions -->
              <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  @click="explainChunk(chunk)"
                  class="p-1.5 text-[var(--text-muted)] hover:text-blue-600 hover:bg-blue-50 rounded transition-colors"
                  title="解释此段"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                  </svg>
                </button>
                <button
                  @click="generateQuiz(chunk)"
                  class="p-1.5 text-[var(--text-muted)] hover:text-green-600 hover:bg-green-50 rounded transition-colors"
                  title="基于此段出题"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                  </svg>
                </button>
                <button
                  @click="copyText(chunk.text)"
                  class="p-1.5 text-[var(--text-muted)] hover:text-[#010120] hover:bg-[var(--bg-tertiary)] rounded transition-colors"
                  title="复制文本"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                </button>
              </div>
            </div>
            
            <!-- Chunk Content -->
            <div class="p-4">
              <p class="text-base text-[var(--text-secondary)] leading-relaxed whitespace-pre-wrap">{{ cleanText(chunk.text) }}</p>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Pagination -->
      <div v-if="filteredChunks.length > pageSize" class="p-4 border-t border-[var(--border-default)] flex items-center justify-between bg-[var(--bg-secondary)] rounded-b-lg">
        <button
          @click="prevPage"
          :disabled="currentPage === 1"
          class="px-4 py-2 text-sm border rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-[var(--bg-secondary)] text-[var(--text-secondary)]"
        >
          上一页
        </button>
        <span class="text-sm text-[var(--text-muted)]">
          {{ currentPage }} / {{ totalPages }}
        </span>
        <button
          @click="nextPage"
          :disabled="currentPage >= totalPages"
          class="px-4 py-2 text-sm border rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-[var(--bg-secondary)] text-[var(--text-secondary)]"
        >
          下一页
        </button>
      </div>
    </div>
    
    <!-- Back to Top Button -->
    <button
      v-if="showBackToTop"
      @click="scrollToTop"
      class="fixed bottom-8 right-8 w-12 h-12 bg-[var(--color-primary)] text-white rounded-full shadow-lg flex items-center justify-center hover:opacity-90 transition-all"
    >
      <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 10l7-7m0 0l7 7m-7-7v18" />
      </svg>
    </button>

    <!-- Toast Notification -->
    <div
      v-if="toast.show"
      class="fixed bottom-8 left-1/2 -translate-x-1/2 bg-[var(--color-primary)] text-white px-4 py-2 rounded-lg shadow-lg text-sm"
    >
      {{ toast.message }}
    </div>

    <!-- Transform Dialog -->
    <TransformDialog
      v-model:visible="showTransformDialog"
      :source-text="transformDocText"
      :source-title="transformDocTitle"
      :document-id="selectedDoc?.id"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useQuizStore } from '../stores/quiz'
import { useDocumentStore } from '../stores/document'
import TransformDialog from '../components/TransformDialog.vue'
import api from '../services/api'

const router = useRouter()
const quizStore = useQuizStore()
const documentStore = useDocumentStore()

const loading = ref(false)
const documents = ref([])
const selectedDoc = ref(null)
const chunks = ref([])
const searchQuery = ref('')
const currentPage = ref(1)
const pageSize = 15
const contentRef = ref(null)
const showBackToTop = ref(false)
const toast = ref({ show: false, message: '' })

// Transform dialog state
const showTransformDialog = ref(false)
const transformDocText = ref('')
const transformDocTitle = ref('')

const filteredChunks = computed(() => {
  if (!searchQuery.value.trim()) {
    return chunks.value
  }
  const query = searchQuery.value.toLowerCase()
  return chunks.value.filter(chunk => 
    chunk.text && chunk.text.toLowerCase().includes(query)
  )
})

const totalPages = computed(() => {
  return Math.ceil(filteredChunks.value.length / pageSize) || 1
})

const paginatedChunks = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return filteredChunks.value.slice(start, start + pageSize)
})

function cleanText(text) {
  if (!text) return ''
  // 处理PDF提取文本的换行问题：单换行替换为空格，保留段落分隔
  return text.replace(/([^。!?！？])\n([^。!?！？])/g, '$1 $2').trim()
}

async function fetchDocuments() {
  loading.value = true
  try {
    await documentStore.fetchDocuments()
    documents.value = documentStore.documents
  } catch (error) {
    console.error('Failed to fetch documents:', error)
  } finally {
    loading.value = false
  }
}

async function selectDocument(doc) {
  selectedDoc.value = doc
  chunks.value = []
  searchQuery.value = ''
  currentPage.value = 1

  try {
    const response = await api.get(`/documents/${doc.id}`)
    if (response.data.chunks) {
      chunks.value = response.data.chunks.map((c, i) => ({ ...c, idx: i }))
    }
  } catch (error) {
    console.error('Failed to load document:', error)
  }
}

function formatSize(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  while (bytes >= 1024 && i < units.length - 1) {
    bytes /= 1024
    i++
  }
  return `${bytes.toFixed(1)} ${units[i]}`
}

function prevPage() {
  if (currentPage.value > 1) {
    currentPage.value--
    scrollToContent()
  }
}

function nextPage() {
  if (currentPage.value < totalPages.value) {
    currentPage.value++
    scrollToContent()
  }
}

function scrollToContent() {
  if (contentRef.value) {
    contentRef.value.scrollTop = 0
  }
}

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function handleScroll() {
  showBackToTop.value = window.scrollY > 300
}

// 操作功能
function showToast(message) {
  toast.value = { show: true, message }
  setTimeout(() => {
    toast.value.show = false
  }, 2000)
}

function copyText(text) {
  navigator.clipboard.writeText(text)
  showToast('已复制到剪贴板')
}

function copyAllText() {
  const text = chunks.value.map(c => c.text).join('\n\n')
  navigator.clipboard.writeText(text)
  showToast('全文已复制到剪贴板')
}

function explainChunk(chunk) {
  // 跳转到问答页面并带入这段文本
  router.push({
    path: '/chat',
    query: { 
      context: chunk.text.substring(0, 500),
      docId: selectedDoc.value?.id 
    }
  })
}

async function generateQuiz(chunk) {
  if (!selectedDoc.value) return
  try {
    showToast('正在生成题目...')
    await quizStore.generateQuizzes([selectedDoc.value.id], 3, 1)
    router.push('/quiz')
  } catch (error) {
    showToast('生成失败，请重试')
  }
}

function openTransform() {
  if (!selectedDoc.value) return
  // Combine all chunks as the source text
  const allText = chunks.value.map(c => c.text).join('\n\n')
  transformDocText.value = allText
  transformDocTitle.value = selectedDoc.value.filename
  showTransformDialog.value = true
}

onMounted(() => {
  fetchDocuments()
  window.addEventListener('scroll', handleScroll)
})

onUnmounted(() => {
  window.removeEventListener('scroll', handleScroll)
})
</script>