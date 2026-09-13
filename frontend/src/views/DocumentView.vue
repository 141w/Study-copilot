<template>
  <div class="max-w-4xl mx-auto px-6 py-8">
    <h1 class="text-2xl font-semibold text-[var(--text-primary)] mb-8">文档阅读</h1>

    <!-- Document List -->
    <div class="mb-8">
      <h2 class="text-lg font-medium text-[var(--text-secondary)] mb-4">选择要阅读的文档</h2>
      <!-- 批次6：文字加载态 → 骨架屏（匹配 2/3 列瓦片网格） -->
      <SkeletonList v-if="documentStore.loading" variant="cards" :count="6" />
      <div v-else-if="documentStore.documents.length === 0" class="text-center py-8 text-[var(--text-muted)]">
        暂无已上传的文档
      </div>
      <div class="mb-4">
        <div class="flex items-center justify-between">
          <p class="text-sm text-[var(--text-muted)]">点击选择文档阅读</p>
          <div class="flex gap-2">
            <el-button
              size="small"
              type="default"
              @click="showClassroomDialog = true"
              :disabled="documentStore.documents.length === 0"
            >
              <el-icon class="w-4 h-4 mr-1"><VideoPlay /></el-icon>
              生成课堂
            </el-button>
          </div>
        </div>
      </div>
      <div v-if="documentStore.documents.length > 0" class="grid grid-cols-2 md:grid-cols-3 gap-4">
        <div
          v-for="doc in documentStore.documents"
          :key="doc.id"
          @click="selectDocument(doc)"
          @keydown.enter="selectDocument(doc)"
          role="button"
          tabindex="0"
          :aria-label="`阅读文档 ${doc.filename}`"
          class="p-4 border rounded-lg cursor-pointer transition-all bg-[var(--surface-card)] shadow-sm hover:border-[var(--border-hover)] hover:bg-[var(--bg-hover)]/30"
          :class="selectedDoc?.id === doc.id ? 'border-l-4 border-l-[var(--color-primary)] ring-1 ring-[var(--color-primary)]' : 'border-[var(--border-default)]'"
        >
          <div class="flex items-center gap-2 mb-2">
            <el-icon class="w-5 h-5 text-[var(--text-secondary)]"><Document /></el-icon>
            <span class="text-xs px-2 py-0.5 rounded flex items-center gap-1"
              :class="doc.status === 'ready' ? 'bg-[var(--color-success-light)] text-[var(--color-success)]' : 'bg-[var(--color-warning-light)] text-[var(--color-warning)]'"
            >
              <el-icon v-if="doc.status === 'processing'" class="is-loading text-[10px]"><Loading /></el-icon>
              {{ doc.status === 'ready' ? '已就绪' : (doc.status === 'processing' ? '处理中' : '错误') }}
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
        <div class="flex items-center gap-2">
          <el-button
            size="small"
            type="primary"
            @click="openOriginalFile"
          >
            <el-icon class="w-4 h-4 mr-1"><View /></el-icon>
            查看原文件
          </el-button>
          <el-button
            size="small"
            type="primary"
            @click="askAboutDoc"
          >
            <el-icon class="w-4 h-4 mr-1"><ChatDotSquare /></el-icon>
            AI 提问
          </el-button>
          <el-button
            size="small"
            type="primary"
            @click="openTransform"
          >
            <el-icon class="w-4 h-4 mr-1"><Switch /></el-icon>
            内容转换
          </el-button>
          <el-button
            size="small"
            type="primary"
            @click="copyAllText"
          >
            <el-icon class="w-4 h-4 mr-1"><CopyDocument /></el-icon>
            复制全文
          </el-button>
        </div>
      </div>

      <!-- Search -->
      <div class="p-4 border-b border-[var(--border-default)] bg-[var(--bg-secondary)] flex items-center gap-3">
        <el-input
          v-model="searchQuery"
          :prefix-icon="Search"
          clearable
          placeholder="搜索文档内容..."
          class="flex-1"
        />
        <span v-if="searchQuery.trim()" class="text-xs text-[var(--text-muted)] flex-shrink-0">
          匹配 {{ filteredChunks.length }} / {{ chunks.length }} 段
        </span>
      </div>

      <!-- Content -->
      <div
        ref="contentRef"
        @scroll.passive="updateScrollVisibility"
        class="p-6 max-h-[70dvh] overflow-y-auto bg-[var(--bg-secondary)]"
      >
        <!-- P3-5：加载 / 搜索无结果 / 无内容 三态区分；
             批次6：加载态由文字改为阅读段落骨架（text 变体） -->
        <SkeletonList v-if="isLoadingContent" variant="text" :count="10" />
        <div v-else-if="selectedDoc?.status === 'processing'" class="text-center py-16 text-[var(--text-muted)] flex flex-col items-center gap-3">
          <el-icon class="is-loading text-2xl text-[var(--color-warning)]"><Loading /></el-icon>
          <p class="text-sm font-medium text-[var(--text-secondary)]">文档正在后台解析与切片中，完成后将自动呈现...</p>
        </div>
        <div v-else-if="filteredChunks.length === 0 && searchQuery.trim()" class="text-center py-12 text-[var(--text-muted)]">
          没有匹配「{{ searchQuery }}」的段落
        </div>
        <div v-else-if="filteredChunks.length === 0" class="text-center py-12 text-[var(--text-muted)]">
          文档内容为空
        </div>
        <div v-else class="space-y-4">
          <div
            v-for="chunk in paginatedChunks"
            :key="chunk.idx"
            class="group bg-[var(--surface-card)] rounded-xl border border-[var(--border-default)] hover:border-[var(--border-hover)] transition-all duration-200"
          >
            <!-- Chunk Header -->
            <div class="flex items-center justify-between px-4 py-3 border-b border-[var(--border-default)] bg-[var(--bg-secondary)]/50 rounded-t-xl">
              <div class="flex items-center gap-3">
                <span class="text-xs font-medium text-[var(--text-muted)]">
                  {{ chunk.page ? `第 ${chunk.page} 页` : `段落 ${filteredChunks.findIndex(c => c.idx === chunk.idx) + 1}` }}
                </span>
              </div>
              <!-- Hover Actions：与顶栏操作同规格 -->
              <div class="flex items-center gap-1.5 md:opacity-0 md:group-hover:opacity-100 focus-within:opacity-100 opacity-100 transition-opacity">
                <el-button
                  size="small"
                  type="primary"
                  @click="explainChunk(chunk)"
                >
                  <el-icon class="w-4 h-4 mr-1"><ChatLineRound /></el-icon>
                  解释此段
                </el-button>
                <el-button
                  size="small"
                  type="primary"
                  @click="generateQuiz(chunk)"
                >
                  <el-icon class="w-4 h-4 mr-1"><EditPen /></el-icon>
                  基于此段出题
                </el-button>
                <el-button
                  size="small"
                  type="primary"
                  @click="copyText(chunk.text)"
                >
                  <el-icon class="w-4 h-4 mr-1"><CopyDocument /></el-icon>
                  复制段落
                </el-button>
              </div>
            </div>

            <!-- Chunk Content（精修批次3：中文长文行高 1.75） -->
            <div class="p-4">
              <p class="text-base text-[var(--text-secondary)] leading-[1.75] whitespace-pre-wrap">
                <template v-for="(part, pIdx) in getHighlightedSegments(cleanText(chunk.text), searchQuery)" :key="pIdx">
                  <mark v-if="part.isMatch" class="bg-amber-200 dark:bg-amber-900/60 text-inherit px-0.5 rounded">{{ part.text }}</mark>
                  <span v-else>{{ part.text }}</span>
                </template>
              </p>
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
    <Transition name="fade">
      <el-tooltip v-if="showBackToTop" content="回到顶部" placement="left">
        <button
          @click="scrollToTop"
          class="fixed bottom-8 right-8 w-10 h-10 rounded-full bg-[var(--surface-card)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--border-default)] hover:border-[var(--border-hover)] hover:bg-[var(--bg-hover)] shadow-sm transition-all flex items-center justify-center cursor-pointer z-40 active:scale-95"
          aria-label="回到顶部"
        >
          <el-icon class="w-4 h-4"><Top /></el-icon>
        </button>
      </el-tooltip>
    </Transition>

    <!-- Transform Dialog -->
    <TransformDialog
      v-model:visible="showTransformDialog"
      :source-text="transformDocText"
      :source-title="transformDocTitle"
      :document-id="selectedDoc?.id"
    />

    <!-- AI 互动课堂生成 -->
    <GenerateClassroomDialog
      v-model="showClassroomDialog"
      :documents="documentStore.documents"
      @generated="onClassroomGenerated"
    />

    <!-- 原始文件本页预览 -->
    <el-dialog
      v-model="showOriginalPreview"
      :title="originalPreviewTitle"
      width="86%"
      top="4vh"
      destroy-on-close
      class="original-file-dialog"
      @closed="closeOriginalPreview"
    >
      <div class="original-preview-body">
        <div v-if="originalPreviewLoading" class="py-16 text-center text-sm text-[var(--text-muted)]">
          正在加载原始文件…
        </div>
        <template v-else>
          <!-- PDF：内嵌浏览器原生预览 -->
          <iframe
            v-if="originalPreviewMime.includes('pdf') && originalPreviewUrl"
            :src="originalPreviewUrl"
            class="w-full h-[72vh] border-0 rounded-lg bg-white"
            title="PDF 预览"
          />
          <!-- 图片 -->
          <img
            v-else-if="originalPreviewMime.startsWith('image/') && originalPreviewUrl"
            :src="originalPreviewUrl"
            class="max-w-full max-h-[72vh] mx-auto rounded-lg"
            alt="文档图片"
          />
          <!-- Markdown / 文本：站内渲染 -->
          <div
            v-else-if="originalPreviewHtml"
            class="prose prose-sm max-w-none overflow-y-auto max-h-[72vh] px-2 text-[var(--text-primary)]"
            v-html="originalPreviewHtml"
          />
          <!-- 其它类型：提示下载 -->
          <div v-else class="py-12 text-center space-y-3">
            <p class="text-sm text-[var(--text-muted)]">
              该文件类型（{{ originalPreviewMime || '未知' }}）暂不支持站内预览
            </p>
            <el-button type="primary" @click="downloadOriginalFile">下载原文件</el-button>
          </div>
        </template>
      </div>
      <template #footer>
        <div class="flex items-center justify-between">
          <span class="text-xs text-[var(--text-muted)]">
            {{ originalPreviewMime }}
          </span>
          <div class="flex gap-2">
            <el-button @click="downloadOriginalFile">下载</el-button>
            <el-button type="primary" @click="showOriginalPreview = false">关闭</el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Document, Switch, CopyDocument, ChatLineRound, EditPen, Top, VideoPlay, Search, ChatDotSquare, Loading, View } from '@/components/icons'
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useQuizStore } from '../stores/quiz'
import { useDocumentStore } from '../stores/document'
import { useToastStore } from '../stores/toast'
import { formatSize, cleanPdfText } from '../composables/useFormat'
import { useMarkdown } from '../composables/useMarkdown'
import type { Document as DocumentModel } from '../types/models'
import TransformDialog from '../components/TransformDialog.vue'
import GenerateClassroomDialog from '../components/classroom/GenerateClassroomDialog.vue'
import SkeletonList from '../components/common/SkeletonList.vue'
import api from '../services/api'

/** 文档 chunk（GET /documents/:id 响应展平 + 视图序号） */
interface DocChunk {
  idx: number
  text: string
  page?: string
}

const router = useRouter()
const route = useRoute()
const quizStore = useQuizStore()
// P1-4：文档列表统一走 document store（原先本地 documents 副本 + 自行 fetch，
// 与 store 数据源分裂）；提示统一走 toast store（原本地 toast 双轨）
const documentStore = useDocumentStore()

function askAboutDoc(): void {
  if (!selectedDoc.value) return
  router.push({ path: '/chat', query: { docId: selectedDoc.value.id } })
}
const toast = useToastStore()
const { renderMarkdown } = useMarkdown()

const selectedDoc = ref<DocumentModel | null>(null)
const chunks = ref<DocChunk[]>([])
// 原始文件本页预览
const showOriginalPreview = ref(false)
const originalPreviewUrl = ref('')
const originalPreviewMime = ref('')
const originalPreviewTitle = ref('')
const originalPreviewHtml = ref('')
const originalPreviewLoading = ref(false)
const originalPreviewError = ref('')
const searchQuery = ref('')
// P3-5：文档内容加载态（区分"加载中"与"搜索无结果"）
const isLoadingContent = ref(false)
const currentPage = ref(1)
const pageSize = 15
const contentRef = ref<HTMLElement | null>(null)
const showBackToTop = ref(false)

// Transform dialog state
const showTransformDialog = ref(false)
const transformDocText = ref('')
const transformDocTitle = ref('')

// AI 互动课堂弹窗
const showClassroomDialog = ref(false)

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

/** 将文本根据搜索关键字拆分为高亮片段（避免 v-html XSS 隐患） */
function getHighlightedSegments(text: string, query: string): Array<{ text: string; isMatch: boolean }> {
  if (!query || !query.trim()) {
    return [{ text, isMatch: false }]
  }
  const q = query.trim()
  const lowerText = text.toLowerCase()
  const lowerQ = q.toLowerCase()
  const segments: Array<{ text: string; isMatch: boolean }> = []
  let lastIndex = 0
  let matchIndex = lowerText.indexOf(lowerQ, lastIndex)

  while (matchIndex !== -1) {
    if (matchIndex > lastIndex) {
      segments.push({ text: text.slice(lastIndex, matchIndex), isMatch: false })
    }
    segments.push({ text: text.slice(matchIndex, matchIndex + q.length), isMatch: true })
    lastIndex = matchIndex + q.length
    matchIndex = lowerText.indexOf(lowerQ, lastIndex)
  }

  if (lastIndex < text.length) {
    segments.push({ text: text.slice(lastIndex), isMatch: false })
  }

  return segments
}

async function selectDocument(doc: DocumentModel, opts?: { highlight?: string; page?: string }): Promise<void> {
  selectedDoc.value = doc
  chunks.value = []
  searchQuery.value = opts?.highlight?.trim() || ''
  currentPage.value = 1
  showBackToTop.value = false
  // 同步选中态到 store（供侧栏等处联动）
  documentStore.selectDocument(doc)

  if (doc.status === 'processing') {
    return
  }

  isLoadingContent.value = true
  try {
    const response = await api.get<{ chunks: DocChunk[] }>(`/documents/${doc.id}`)
    if (response.data.chunks) {
      chunks.value = response.data.chunks.map((c, i) => ({ ...c, idx: i }))
    }
    // 深链：按页码把列表滚到该页附近（页码在 chunk.page 元数据上）
    if (opts?.page) {
      const page = String(opts.page)
      const idx = chunks.value.findIndex(c => String(c.page ?? '') === page)
      if (idx >= 0) {
        currentPage.value = Math.floor(idx / pageSize) + 1
      }
    }
    if (searchQuery.value) {
      await nextTick()
      scrollToFirstMatch()
    }
  } catch (error) {
    console.error('Failed to load document:', error)
    toast.error('文档内容加载失败')
  } finally {
    isLoadingContent.value = false
  }
}

/** 搜索定位后滚到第一个高亮段（阅读区内部滚动容器） */
function scrollToFirstMatch(): void {
  nextTick(() => {
    const el = contentRef.value?.querySelector('mark')
    const fallback = contentRef.value?.querySelector('.space-y-4 > div')
    const target = el || fallback
    if (target && contentRef.value) {
      target.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  })
}

/** 笔记/聊天深链：/documents?doc=&page=&q= */
async function applyDeepLinkFromRoute(): Promise<void> {
  const docId = route.query.doc
  if (typeof docId !== 'string' || !docId) return
  await documentStore.fetchDocuments()
  const doc = documentStore.documents.find(d => d.id === docId)
  if (!doc) {
    toast.error('未找到对应文档')
    return
  }
  const page = typeof route.query.page === 'string' ? route.query.page : undefined
  const q = typeof route.query.q === 'string' ? route.query.q : undefined
  await selectDocument(doc, { highlight: q, page })
}

// 当选中的文档在后台完成解析切片后，自动加载内容
watch(
  () => documentStore.documents.find(d => d.id === selectedDoc.value?.id),
  (updatedDoc) => {
    if (updatedDoc && selectedDoc.value) {
      const wasProcessing = selectedDoc.value.status === 'processing'
      selectedDoc.value = updatedDoc
      if (wasProcessing && updatedDoc.status === 'ready' && chunks.value.length === 0) {
        selectDocument(updatedDoc)
      }
    }
  }
)

function scrollToContent(): void {
  if (contentRef.value) {
    contentRef.value.scrollTop = 0
  }
  updateScrollVisibility()
}

function updateScrollVisibility(): void {
  const contentScrolled = (contentRef.value?.scrollTop ?? 0) > 200
  const windowScrolled = window.scrollY > 200
  showBackToTop.value = contentScrolled || windowScrolled
}

function scrollToTop(): void {
  if (contentRef.value && contentRef.value.scrollTop > 0) {
    contentRef.value.scrollTo({ top: 0, behavior: 'smooth' })
  }
  if (window.scrollY > 0) {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
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

/** 在本页弹层预览原始文件（PDF/图片/Markdown/文本）；其它类型提供下载 */
async function openOriginalFile(): Promise<void> {
  if (!selectedDoc.value) return
  originalPreviewLoading.value = true
  originalPreviewError.value = ''
  try {
    const resp = await api.get(`/documents/${selectedDoc.value.id}/file`, {
      responseType: 'blob',
    })
    const mime = (resp.headers['content-type'] as string) || 'application/octet-stream'
    const blob = new Blob([resp.data], { type: mime })
    originalPreviewMime.value = mime
    originalPreviewUrl.value = URL.createObjectURL(blob)

    const isTextish =
      mime.includes('markdown') ||
      mime.includes('text/') ||
      mime.includes('json') ||
      /\.(md|txt|json|csv)$/i.test(selectedDoc.value.filename || '')

    if (isTextish) {
      const text = await blob.text()
      originalPreviewHtml.value = renderMarkdown(text)
    } else {
      originalPreviewHtml.value = ''
    }

    originalPreviewTitle.value = selectedDoc.value.filename || '原始文件'
    showOriginalPreview.value = true
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    toast.error(typeof detail === 'string' ? detail : '原始文件不可用')
  } finally {
    originalPreviewLoading.value = false
  }
}

function downloadOriginalFile(): void {
  if (!originalPreviewUrl.value) return
  const a = document.createElement('a')
  a.href = originalPreviewUrl.value
  a.download = originalPreviewTitle.value || 'document'
  a.click()
}

function closeOriginalPreview(): void {
  showOriginalPreview.value = false
  if (originalPreviewUrl.value) {
    URL.revokeObjectURL(originalPreviewUrl.value)
    originalPreviewUrl.value = ''
  }
  originalPreviewHtml.value = ''
  originalPreviewMime.value = ''
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

// AI 互动课堂：课堂生成完成回调
function onClassroomGenerated(_result: { jobId: string; courseId?: string }): void {
  toast.success('课堂生成任务已提交！')
}

onMounted(() => {
  documentStore.fetchDocuments()
  applyDeepLinkFromRoute()
  window.addEventListener('scroll', updateScrollVisibility, { passive: true })
})

onUnmounted(() => {
  window.removeEventListener('scroll', updateScrollVisibility)
})
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(6px);
}
</style>
