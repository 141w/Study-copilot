<template>
  <el-dialog
    v-model="localVisible"
    title="从 URL 导入"
    width="500px"
    :close-on-click-modal="false"
    @closed="onClosed"
  >
    <label class="block text-sm font-medium text-[var(--text-secondary)] mb-2">网页地址</label>
    <el-input
      v-model="url"
      type="url"
      placeholder="https://example.com/article"
      @keydown.enter="importUrl"
    />
    <p class="text-xs text-[var(--text-muted)] mt-2">输入网页 URL，系统将自动提取正文内容并保存为文档</p>

    <!-- Status Messages -->
    <div v-if="error" class="mt-4 p-3 bg-[var(--color-error-light)] border border-[var(--color-error)]/20 rounded-xl text-sm text-[var(--color-error)]">
      {{ error }}
    </div>
    <div v-if="success" class="mt-4 p-3 bg-[var(--color-success-light)] border border-[var(--color-success)]/20 rounded-xl text-sm text-[var(--color-success)]">
      导入成功！已生成 {{ chunkCount }} 个知识块
    </div>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button
        type="primary"
        :disabled="!url.trim()"
        :loading="loading"
        @click="importUrl"
      >
        {{ loading ? '导入中...' : '开始导入' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, onBeforeUnmount } from 'vue'
import api from '../services/api'
import type { Document as DocumentModel } from '../types/models'

const props = withDefaults(defineProps<{
  visible?: boolean
}>(), {
  visible: false
})

const emit = defineEmits<{
  'update:visible': [value: boolean]
  close: []
  imported: [doc: DocumentModel]
}>()

const url = ref('')
const loading = ref(false)
const error = ref('')
const success = ref(false)
const chunkCount = ref(0)
const localVisible = ref(false)
// P1-2：自动关闭 timer 引用
let autoCloseTimer: ReturnType<typeof setTimeout> | null = null

watch(() => props.visible, (val) => {
  localVisible.value = val
  if (val) {
    url.value = ''
    error.value = ''
    success.value = false
  }
})

function close(): void {
  if (autoCloseTimer) {
    clearTimeout(autoCloseTimer)
    autoCloseTimer = null
  }
  url.value = ''
  error.value = ''
  success.value = false
  localVisible.value = false
}

onBeforeUnmount(() => {
  // P1-2：组件卸载时清理自动关闭 timer
  if (autoCloseTimer) {
    clearTimeout(autoCloseTimer)
    autoCloseTimer = null
  }
})

function onClosed(): void {
  emit('update:visible', false)
  emit('close')
}

async function importUrl(): Promise<void> {
  if (!url.value.trim() || loading.value) return

  loading.value = true
  error.value = ''
  success.value = false

  try {
    const response = await api.post<DocumentModel>('/documents/from-url', {
      url: url.value.trim()
    })
    chunkCount.value = (response.data as unknown as { chunk_count?: number }).chunk_count || 0
    success.value = true
    emit('imported', response.data)

    // Auto-close after 2 seconds（P1-2：timer 存引用，卸载/关闭时清理）
    if (autoCloseTimer) clearTimeout(autoCloseTimer)
    autoCloseTimer = setTimeout(() => {
      close()
      autoCloseTimer = null
    }, 2000)
  } catch (err) {
    const axiosError = err as { response?: { data?: { detail?: string } } }
    const detail = axiosError.response?.data?.detail || ''
    if (detail.includes('无法访问')) {
      error.value = '无法访问该 URL，请检查链接是否正确'
    } else if (detail.includes('无法从该 URL 中提取')) {
      error.value = '无法从该页面提取文本内容'
    } else {
      error.value = detail || '导入失败，请重试'
    }
  } finally {
    loading.value = false
  }
}
</script>
