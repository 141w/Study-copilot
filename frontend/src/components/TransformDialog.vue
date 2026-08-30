<template>
  <BaseDialog
    :visible="visible"
    title="内容转换"
    size="lg"
    @update:visible="$emit('update:visible', $event)"
    @close="close"
  >
    <!-- Transform Type Selection -->
    <div class="mb-4">
      <label class="block text-sm font-medium text-[var(--text-secondary)] mb-2">选择转换类型</label>
      <div class="grid grid-cols-2 gap-2">
        <button
          v-for="t in transformations"
          :key="t.key"
          @click="selectedType = t.key"
          class="p-3 text-left border rounded-lg transition-all text-sm"
          :class="selectedType === t.key
            ? 'border-[#010120] bg-[var(--bg-secondary)] ring-1 ring-[#010120]'
            : 'border-[var(--border-default)] hover:border-[var(--border-hover)] hover:bg-[var(--bg-secondary)]'"
        >
          <div class="font-medium text-[var(--text-primary)]">{{ t.name }}</div>
          <div class="text-xs text-[var(--text-muted)] mt-0.5">{{ t.description }}</div>
        </button>
      </div>
    </div>

    <!-- Result -->
    <div v-if="result" class="mt-4">
      <div class="flex items-center justify-between mb-2">
        <label class="block text-sm font-medium text-[var(--text-secondary)]">转换结果</label>
        <button
          @click="copyResult"
          class="text-xs text-[var(--text-muted)] hover:text-[#010120] transition-colors flex items-center gap-1"
        >
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
          复制
        </button>
      </div>
      <div
        class="p-4 bg-[var(--bg-secondary)] rounded-lg border border-[var(--border-default)] max-h-60 overflow-y-auto text-sm text-[var(--text-secondary)] whitespace-pre-wrap leading-relaxed"
      >{{ result }}</div>
    </div>

    <template #footer-left>
      <span v-if="copied" class="text-xs text-green-600">已复制到剪贴板</span>
      <span v-else class="text-xs text-[var(--text-muted)]">选择类型后点击转换</span>
    </template>

    <template #footer>
      <BaseButton variant="secondary" @click="close">关闭</BaseButton>
      <BaseButton
        :disabled="!selectedType"
        :loading="loading"
        @click="execute"
      >
        {{ loading ? '转换中...' : '开始转换' }}
      </BaseButton>
    </template>
  </BaseDialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import api from '../services/api'
import BaseDialog from './common/BaseDialog.vue'
import BaseButton from './common/BaseButton.vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  sourceText: { type: String, default: '' },
  sourceTitle: { type: String, default: '' },
  noteId: { type: String, default: null },
  documentId: { type: String, default: null }
})

const emit = defineEmits(['update:visible', 'close'])

const transformations = ref([])
const selectedType = ref('')
const result = ref('')
const loading = ref(false)
const copied = ref(false)

// Fetch available transformations
async function fetchTransformations() {
  try {
    const response = await api.get('/transform/transformations')
    transformations.value = response.data
  } catch (error) {
    console.error('Failed to fetch transformations:', error)
  }
}

async function execute() {
  if (!selectedType.value) return

  loading.value = true
  result.value = ''
  copied.value = false

  try {
    const payload = {
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

    const response = await api.post('/transform', payload)
    result.value = response.data.result
  } catch (error) {
    console.error('Transform failed:', error)
    result.value = '转换失败，请重试'
  } finally {
    loading.value = false
  }
}

function copyResult() {
  if (result.value) {
    navigator.clipboard.writeText(result.value)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  }
}

function close() {
  emit('update:visible', false)
  emit('close')
}

// Fetch transformations when dialog becomes visible
watch(() => props.visible, (val) => {
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
