<template>
  <div class="max-w-4xl mx-auto px-6 py-8">
    <h1 class="text-2xl font-semibold text-gray-900 mb-8">上传文档</h1>
    
<!-- Upload Area -->
    <div 
      class="border-2 border-dashed border-gray-200 rounded-xl p-12 text-center mb-8"
      :class="{ 'border-[#010120] bg-gray-50': isDragging }"
      @dragover.prevent="isDragging = true"
      @dragleave.prevent="isDragging = false"
      @drop.prevent="handleDrop"
    >
      <div class="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
        <svg class="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
        </svg>
      </div>
      <p class="text-gray-600 mb-2">拖拽文档到此处，或点击上传</p>
      <input
        type="file"
        accept=".pdf,.docx,.pptx"
        class="hidden"
        ref="fileInput"
        @change="handleFileSelect"
      />
      <button 
        @click="$refs.fileInput.click()"
        class="btn-secondary"
      >
        选择文件
      </button>
      <p class="text-sm text-gray-400 mt-4">支持 PDF、DOCX、PPTX 格式，最大 50MB</p>
      <div class="flex justify-center gap-4 mt-3">
        <span class="text-xs px-2 py-1 bg-red-50 text-red-600 rounded">PDF</span>
        <span class="text-xs px-2 py-1 bg-blue-50 text-blue-600 rounded">Word</span>
        <span class="text-xs px-2 py-1 bg-orange-50 text-orange-600 rounded">PowerPoint</span>
      </div>
    </div>

    <!-- Document List -->
    <div class="card">
      <div class="p-4 border-b border-gray-100">
        <h2 class="font-semibold text-gray-900">我的文档</h2>
      </div>
      
      <div v-if="documentStore.loading" class="p-8 text-center">
        <svg class="w-8 h-8 animate-spin mx-auto text-gray-400" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
      </div>
      
      <div v-else-if="documentStore.documents.length === 0" class="p-8 text-center text-gray-500">
        暂无文档，请先上传
      </div>
      
      <div v-else class="divide-y divide-gray-100">
        <div 
          v-for="doc in documentStore.documents" 
          :key="doc.id"
          class="p-4 flex items-center gap-4"
        >
          <div class="w-10 h-10 bg-red-50 rounded-lg flex items-center justify-center">
            <svg class="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          
          <div class="flex-1">
            <h3 class="font-medium text-gray-900">{{ doc.filename }}</h3>
            <p class="text-sm text-gray-500">
              {{ doc.chunk_count }} chunks · 
              <span :class="statusColor(doc.status)">{{ statusText(doc.status) }}</span>
            </p>
          </div>
          
          <button 
            @click="deleteDoc(doc.id)"
            class="text-gray-400 hover:text-red-500 transition-colors"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useDocumentStore } from '../stores/document'
import { useToastStore } from '../stores/toast'

const documentStore = useDocumentStore()
const toastStore = useToastStore()
const isDragging = ref(false)
const fileInput = ref(null)

function handleDrop(e) {
  isDragging.value = false
  const files = e.dataTransfer.files
  if (files.length > 0) {
    uploadFile(files[0])
  }
}

function handleFileSelect(e) {
  const files = e.target.files
  if (files.length > 0) {
    uploadFile(files[0])
  }
}

async function uploadFile(file) {
  try {
    await documentStore.uploadDocument(file)
    toastStore.success('文档上传成功')
  } catch (error) {
    console.error('Upload failed:', error)
    const message = error.response?.data?.detail || '上传失败，请重试'
    toastStore.error(message)
  }
}

async function deleteDoc(docId) {
  await documentStore.deleteDocument(docId)
}

function statusColor(status) {
  switch (status) {
    case 'ready': return 'text-green-500'
    case 'processing': return 'text-yellow-500'
    case 'error': return 'text-red-500'
    default: return 'text-gray-500'
  }
}

function statusText(status) {
  switch (status) {
    case 'ready': return '就绪'
    case 'processing': return '处理中'
    case 'error': return '错误'
    default: return '待处理'
  }
}

onMounted(() => {
  documentStore.fetchDocuments()
})
</script>