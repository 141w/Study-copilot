<template>
  <el-dialog
    v-model="localVisible"
    title="内容转换"
    width="60%"
    :close-on-click-modal="false"
    @closed="onClosed"
  >
    <!-- Transform Type Selection -->
    <div class="mb-4">
      <label class="block text-sm font-medium text-[var(--text-secondary)] mb-2">选择转换类型</label>
      <div class="grid grid-cols-2 gap-2">
        <button
          v-for="t in transformations"
          :key="t.key"
          @click="selectedType = t.key"
          class="p-3 text-left border rounded-md transition-all text-sm"
          :class="selectedType === t.key
            ? 'border-[var(--color-primary)] bg-[var(--bg-secondary)] ring-1 ring-[var(--color-primary)]'
            : 'border-[var(--border-default)] hover:border-[var(--border-hover)] hover:bg-[var(--bg-secondary)]'"
        >
          <div class="font-medium text-[var(--text-primary)]">{{ t.name }}</div>
          <div class="text-xs text-[var(--text-muted)] mt-0.5">{{ t.description }}</div>
        </button>
      </div>
    </div>

      <!-- F3：转换中骨架占位（匹配结果框形状），替代正文区空白 -->
    <div v-if="loading" class="mt-4">
      <div class="flex items-center justify-between mb-2">
        <label class="block text-sm font-medium text-[var(--text-secondary)]">转换结果</label>
      </div>
      <div class="p-4 bg-[var(--bg-secondary)] rounded-lg border border-[var(--border-default)] space-y-3" aria-busy="true" role="status" aria-label="转换中">
        <div class="skeleton-block h-3.5 rounded w-11/12"></div>
        <div class="skeleton-block h-3.5 rounded w-full"></div>
        <div class="skeleton-block h-3.5 rounded w-4/5"></div>
        <div class="skeleton-block h-3.5 rounded w-3/5"></div>
      </div>
    </div>

    <!-- Result -->
    <div v-else-if="result" class="mt-4">
      <div class="flex items-center justify-between mb-2">
        <label class="block text-sm font-medium text-[var(--text-secondary)]">转换结果</label>
        <button
          @click="copyResult"
          class="text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors flex items-center gap-1"
        >
          <el-icon class="w-3.5 h-3.5"><CopyDocument /></el-icon>
          复制
        </button>
      </div>
      <div
        class="p-4 bg-[var(--bg-secondary)] rounded-lg border border-[var(--border-default)] max-h-60 overflow-y-auto text-sm text-[var(--text-secondary)] whitespace-pre-wrap leading-relaxed"
      >{{ result }}</div>
    </div>

    <template #footer>
      <div class="flex gap-2">
        <span v-if="copied" class="text-xs text-[var(--color-success)]">已复制到剪贴板</span>
        <span v-else class="text-xs text-[var(--text-muted)]">选择类型后点击转换</span>
        <div class="flex-1"></div>
        <el-button @click="close">关闭</el-button>
        <el-button
          type="primary"
          :disabled="!selectedType"
          :loading="loading"
          @click="execute"
        >
          {{ loading ? '转换中...' : '开始转换' }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { CopyDocument } from '@/components/icons'
import api from '../services/api'
import type { Transformation } from '../types/models'

const props = withDefaults(defineProps<{
  visible?: boolean
  sourceText?: string
  sourceTitle?: string
  noteId?: string | null
  documentId?: string | null
}>(), {
  visible: false,
  sourceText: '',
  sourceTitle: '',
  noteId: null,
  documentId: null
})

const emit = defineEmits<{
  'update:visible': [value: boolean]
  close: []
}>()

const transformations = ref<Transformation[]>([])
const selectedType = ref('')
const result = ref('')
const loading = ref(false)
const copied = ref(false)
const localVisible = ref(false)

watch(() => props.visible, (val) => {
  localVisible.value = val
})

function close(): void {
  localVisible.value = false
}

function onClosed(): void {
  emit('update:visible', false)
  emit('close')
}

// Fetch available transformations
async function fetchTransformations(): Promise<void> {
  try {
    const response = await api.get<Transformation[]>('/transform/transformations')
    transformations.value = response.data
  } catch (error) {
    console.error('Failed to fetch transformations:', error)
  }
}

async function execute(): Promise<void> {
  if (!selectedType.value) return

  loading.value = true
  result.value = ''
  copied.value = false

  try {
    const payload: Record<string, string> = {
      transform_type: selectedType.value,
      source_title: props.sourceTitle
    }

    if (props.noteId) {
      payload.note_id = props.noteId
    } else if (props.documentId) {
      payload.document_id = props.documentId
    } else {
      payload.source_text = props.sourceText
    }

    const response = await api.post<{ result: string }>('/transform', payload)
    result.value = response.data.result
  } catch (error) {
    console.error('Transform failed:', error)
    result.value = '转换失败，请重试'
  } finally {
    loading.value = false
  }
}

function copyResult(): void {
  if (result.value) {
    navigator.clipboard.writeText(result.value)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  }
}

// Fetch transformations when dialog becomes visible
watch(() => localVisible.value, (val) => {
  if (val && transformations.value.length === 0) {
    fetchTransformations()
  }
  if (val) {
    result.value = ''
    selectedType.value = ''
    copied.value = false
  }
})
</script>

<style scoped>
/* F3：转换中骨架条（token 底色 + shimmer；reduced-motion 下停用扫光） */
.skeleton-block {
  background-color: var(--bg-tertiary);
  position: relative;
  overflow: hidden;
}
.skeleton-block::after {
  content: '';
  position: absolute;
  inset: 0;
  transform: translateX(-100%);
  background: linear-gradient(90deg, transparent, color-mix(in srgb, var(--text-primary) 4%, transparent), transparent);
  animation: transform-skeleton-shimmer 1.5s infinite;
}
@keyframes transform-skeleton-shimmer {
  100% { transform: translateX(100%); }
}
@media (prefers-reduced-motion: reduce) {
  .skeleton-block::after { animation: none; }
}
</style>
