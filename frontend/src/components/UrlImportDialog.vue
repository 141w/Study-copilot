<template>
  <BaseDialog
    :visible="visible"
    title="从 URL 导入"
    size="md"
    @update:visible="$emit('update:visible', $event)"
    @close="close"
  >
    <label class="block text-sm font-medium text-[var(--text-secondary)] mb-2">网页地址</label>
    <input
      v-model="url"
      type="url"
      placeholder="https://example.com/article"
      class="w-full px-4 py-2.5 border border-[var(--border-default)] rounded-lg bg-white focus:outline-none focus:border-[#010120] focus:ring-1 focus:ring-[#010120] text-sm"
      @keydown.enter="importUrl"
    />
    <p class="text-xs text-[var(--text-muted)] mt-2">输入网页 URL，系统将自动提取正文内容并保存为文档</p>

    <!-- Status Messages -->
    <div v-if="error" class="mt-4 p-3 bg-red-50 border border-red-100 rounded-lg text-sm text-red-600">
      {{ error }}
    </div>
    <div v-if="success" class="mt-4 p-3 bg-green-50 border border-green-100 rounded-lg text-sm text-green-700">
      导入成功！已生成 {{ chunkCount }} 个知识块
    </div>

    <template #footer>
      <BaseButton variant="secondary" @click="close">取消</BaseButton>
      <BaseButton
        :disabled="!url.trim()"
        :loading="loading"
        @click="importUrl"
      >
        {{ loading ? '导入中...' : '开始导入' }}
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
  visible: { type: Boolean, default: false }
})

const emit = defineEmits(['update:visible', 'close', 'imported'])

const url = ref('')
const loading = ref(false)
const error = ref('')
const success = ref(false)
const chunkCount = ref(0)

async function importUrl() {
  if (!url.value.trim() || loading.value) return

  loading.value = true
  error.value = ''
  success.value = false

  try {
    const response = await api.post('/documents/from-url', {
      url: url.value.trim()
    })
    chunkCount.value = response.data.chunk_count || 0
    success.value = true
    emit('imported', response.data)

    // Auto-close after 2 seconds
    setTimeout(() => {
      close()
    }, 2000)
  } catch (err) {
    const detail = err.response?.data?.detail || ''
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

function close() {
  url.value = ''
  error.value = ''
  success.value = false
  emit('update:visible', false)
  emit('close')
}

watch(() => props.visible, (val) => {
  if (val) {
    url.value = ''
    error.value = ''
    success.value = false
  }
})
</script>
