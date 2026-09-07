<template>
  <div class="max-w-4xl mx-auto px-6 py-8">
    <h1 class="text-2xl font-semibold text-[var(--text-primary)] mb-8">上传文档</h1>
    
<!-- Upload Area -->
    <div
      ref="uploadArea"
      class="border-2 border-dashed border-[var(--border-hover)] rounded-2xl p-12 text-center mb-8"
      :class="{ 'border-[var(--color-primary)] bg-[var(--bg-secondary)]': isDragging }"
      @dragover.prevent="isDragging = true"
      @dragleave.prevent="isDragging = false"
      @drop.prevent="handleDrop"
    >
      <div class="w-16 h-16 bg-[var(--bg-tertiary)] rounded-full flex items-center justify-center mx-auto mb-4">
        <el-icon class="w-8 h-8 text-[var(--text-muted)]"><Upload /></el-icon>
      </div>
      <p class="text-[var(--text-secondary)] mb-2">拖拽文档到此处，或点击上传</p>
      <input
        type="file"
        accept=".pdf,.docx,.pptx"
        class="hidden"
        ref="fileInput"
        @change="handleFileSelect"
      />
      <el-button
        @click="fileInput?.click()"
        :disabled="uploading"
      >
        {{ uploading ? '上传中...' : '选择文件' }}
      </el-button>
      <p class="text-sm text-[var(--text-muted)] mt-4">支持 PDF、DOCX、PPTX 格式，最大 50MB</p>
      <div class="flex justify-center gap-4 mt-3">
        <span class="text-xs px-2 py-1 bg-[var(--bg-tertiary)] text-[var(--text-secondary)] rounded border border-[var(--border-default)]">PDF</span>
        <span class="text-xs px-2 py-1 bg-[var(--bg-tertiary)] text-[var(--text-secondary)] rounded border border-[var(--border-default)]">Word</span>
        <span class="text-xs px-2 py-1 bg-[var(--bg-tertiary)] text-[var(--text-secondary)] rounded border border-[var(--border-default)]">PowerPoint</span>
      </div>
    </div>

    <!-- URL Import Button（按钮尺寸统一：42px 手写钮换 el-button 32px 基准） -->
    <div class="flex justify-center mb-8">
      <el-button @click="showUrlDialog = true">
        <el-icon class="mr-1"><Link /></el-icon>
        从网页 URL 导入
      </el-button>
    </div>

    <!-- URL Import Dialog -->
    <UrlImportDialog
      v-model:visible="showUrlDialog"
      @imported="onUrlImported"
    />

    <!-- Document List -->
    <div ref="docList" class="card">
      <div class="p-4 border-b border-[var(--border-default)]">
        <h2 class="font-semibold text-[var(--text-primary)]">我的文档</h2>
      </div>
      
      <!-- P1-2：骨架屏匹配行式列表形状（§4.5） -->
      <SkeletonList v-if="documentStore.loading" variant="rows" :count="3" />
      
      <div v-else-if="documentStore.documents.length === 0" class="p-8 text-center text-[var(--text-muted)]">
        暂无文档，请先上传
      </div>
      
      <div v-else class="divide-y divide-[var(--border-default)]">
        <div 
          v-for="doc in documentStore.documents" 
          :key="doc.id"
          class="p-4 flex items-center gap-4"
        >
          <div class="w-10 h-10 bg-[var(--bg-tertiary)] rounded-lg flex items-center justify-center">
            <el-icon class="w-5 h-5 text-[var(--text-secondary)]"><Document /></el-icon>
          </div>
          
          <div class="flex-1 min-w-0">
            <h3 class="font-medium text-[var(--text-primary)] truncate">{{ doc.filename }}</h3>
            <p class="text-sm text-[var(--text-muted)] flex items-center gap-1.5 mt-0.5">
              <span v-if="doc.file_size">{{ formatSize(doc.file_size) }} ·</span>
              <template v-if="doc.status === 'processing'">
                <span class="inline-flex items-center gap-1.5 text-[var(--color-warning)] font-medium">
                  <el-icon class="is-loading text-xs"><Loading /></el-icon>
                  正在解析与切片...
                </span>
              </template>
              <template v-else>
                <span>{{ doc.chunk_count }} 个知识块</span>
                <span>·</span>
                <span :class="statusColor(doc.status)">{{ statusText(doc.status) }}</span>
              </template>
            </p>
          </div>
          
          <el-button
            @click="confirmDeleteDoc(doc)"
            :title="`删除 ${doc.filename}`"
            :aria-label="`删除文档 ${doc.filename}`"
          >
            <el-icon class="w-4 h-4"><Delete /></el-icon>
          </el-button>
        </div>
      </div>
    </div>

    <!-- Delete Confirmation（P2-2：ConfirmDialog 替换手写 el-dialog） -->
    <ConfirmDialog
      v-model="showDeleteConfirm"
      title="删除文档"
      :message="`确定要删除「${deletingDoc?.filename}」吗？其向量索引将一并移除，此操作不可撤销。`"
      :loading="deleting"
      @confirm="doDeleteDoc"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import gsap from 'gsap'
import { Upload, Link, Document, Delete, Loading } from '@/components/icons'
import { useDocumentStore } from '../stores/document'
import { useToastStore } from '../stores/toast'
import type { Document as DocumentModel } from '../types/models'
import UrlImportDialog from '../components/UrlImportDialog.vue'
import ConfirmDialog from '../components/common/ConfirmDialog.vue'
import SkeletonList from '../components/common/SkeletonList.vue'
import { useReducedMotion } from '../composables/useReducedMotion'
import { formatSize } from '../composables/useFormat'

const documentStore = useDocumentStore()
const toastStore = useToastStore()
// P1-1：GSAP 动画降级（prefers-reduced-motion）
const { prefersReduced } = useReducedMotion()
const isDragging = ref(false)
const uploading = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const uploadArea = ref<HTMLElement | null>(null)
const docList = ref<HTMLElement | null>(null)
const showUrlDialog = ref(false)
let ctx: gsap.Context | null = null

function handleDrop(e: DragEvent): void {
  isDragging.value = false
  const files = e.dataTransfer?.files
  if (files && files.length > 0) {
    if (files[0].size > 50 * 1024 * 1024) {
      toastStore.error('文件大小超过 50MB 限制')
      return
    }
    uploadFile(files[0])
  }
}

function handleFileSelect(e: Event): void {
  const files = (e.target as HTMLInputElement).files
  if (files && files.length > 0) {
    if (files[0].size > 50 * 1024 * 1024) {
      toastStore.error('文件大小超过 50MB 限制')
      return
    }
    uploadFile(files[0])
  }
}

async function uploadFile(file: File): Promise<void> {
  uploading.value = true
  try {
    const result = await documentStore.uploadDocument(file)
    if (result?.status === 'processing') {
      toastStore.info('文档上传成功，正在后台解析与切片...')
    } else {
      const chunkCount = result?.chunk_count ?? 0
      toastStore.success(`文档上传成功！共生成 ${chunkCount} 个知识块`)
    }
  } catch (error) {
    console.error('Upload failed:', error)
    const axiosError = error as { response?: { data?: { detail?: string } } }
    const detail = axiosError.response?.data?.detail || ''
    let message: string
    if (detail.includes('文档解析失败')) {
      message = '无法解析此文档，请确认文件未损坏'
    } else if (detail.includes('文档内容不足')) {
      message = '文档内容太少，无法生成知识块'
    } else if (detail.includes('文件过大')) {
      message = '文件超过 50MB 限制'
    } else {
      message = '上传失败，请重试'
    }
    toastStore.error(message)
  } finally {
    uploading.value = false
  }
}

// P0-4：删除确认（原为无确认直接删）
const showDeleteConfirm = ref(false)
const deletingDoc = ref<DocumentModel | null>(null)
const deleting = ref(false)

function confirmDeleteDoc(doc: DocumentModel): void {
  deletingDoc.value = doc
  showDeleteConfirm.value = true
}

async function doDeleteDoc(): Promise<void> {
  if (!deletingDoc.value) return
  deleting.value = true
  try {
    await documentStore.deleteDocument(deletingDoc.value.id)
    toastStore.success('文档已删除')
    showDeleteConfirm.value = false
    deletingDoc.value = null
  } catch (_e) {
    toastStore.error('删除失败，请重试')
  } finally {
    deleting.value = false
  }
}

// 修复（2026-08-19）：模板绑定了 @imported="onUrlImported" 但函数未定义，
// URL 导入成功后列表不刷新、无提示。补上 handler。
function onUrlImported(doc: { filename?: string; status?: string; chunk_count?: number } | null): void {
  if (doc?.status === 'processing') {
    toastStore.info(`URL 导入成功，正在后台解析与切片：${doc?.filename || '文档'}`)
  } else {
    toastStore.success(`URL 导入成功：${doc?.filename || '文档已加入列表'}`)
  }
  documentStore.fetchDocuments(true)
}

function statusColor(status: string): string {
  switch (status) {
    case 'ready': return 'text-[var(--color-success)]'
    case 'processing': return 'text-[var(--color-warning)]'
    case 'error': return 'text-[var(--color-error)]'
    default: return 'text-[var(--text-muted)]'
  }
}

function statusText(status: string): string {
  switch (status) {
    case 'ready': return '就绪'
    case 'processing': return '处理中'
    case 'error': return '错误'
    default: return '待处理'
  }
}

onMounted(() => {
  documentStore.fetchDocuments()

  // P1-1：减少动态偏好下跳过入场动画
  if (prefersReduced.value) return
  ctx = gsap.context(() => {
    gsap.from(uploadArea.value, {
      y: 20,
      opacity: 0,
      duration: 0.5,
      ease: 'power2.out'
    })

    const cards = docList.value?.querySelectorAll('.divide-y > div')
    if (cards?.length) {
      gsap.from(cards, {
        y: 10,
        opacity: 0,
        duration: 0.4,
        stagger: 0.05,
        ease: 'power2.out'
      })
    }
  })
})

onUnmounted(() => {
  ctx?.revert()
})
</script>