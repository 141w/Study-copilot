<template>
  <el-dialog
    v-model="localVisible"
    title="生成 OpenMAIC 课堂"
    width="520px"
    :close-on-click-modal="false"
    @closed="onClosed"
  >
    <div class="space-y-4">
      <!-- 主题输入 -->
      <div>
        <label class="block text-sm font-medium text-[var(--text-secondary)] mb-1.5">
          课程主题 <span class="text-[var(--color-error)]">*</span>
        </label>
        <el-input
          v-model="requirement"
          type="textarea"
          :rows="2"
          placeholder="e.g. 线性代数第一章：向量空间基础"
          maxlength="500"
          show-word-limit
        />
      </div>

      <!-- 文档选择 -->
      <div>
        <label class="block text-sm font-medium text-[var(--text-secondary)] mb-1.5">
          选择参考文档（最多 5 篇）
        </label>
        <div class="border border-[var(--border-default)] rounded-lg p-2 max-h-48 overflow-y-auto">
          <label
            v-for="doc in documents"
            :key="doc.id"
            class="flex items-center gap-2 px-3 py-2 rounded-md cursor-pointer transition-colors text-sm"
            :class="selectedDocs.includes(doc.id)
              ? 'bg-[var(--color-primary)] text-[var(--text-inverse)]'
              : 'bg-[var(--surface-card)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]'"
          >
            <input
              type="checkbox"
              :value="doc.id"
              :checked="selectedDocs.includes(doc.id)"
              class="hidden"
              @change="toggleDoc(doc.id)"
            />
            <span class="truncate">{{ doc.filename }}</span>
            <span class="text-xs opacity-60">{{ doc.status }}</span>
          </label>
          <p v-if="documents.length === 0" class="text-sm text-[var(--text-muted)] text-center py-3">
            暂无已上传的文档
          </p>
        </div>
      </div>

      <!-- 高级选项 -->
      <div class="grid grid-cols-3 gap-4 py-1">
        <label class="flex items-center gap-2 text-sm cursor-pointer">
          <el-switch v-model="enableWebSearch" size="small" />
          <span class="text-[var(--text-secondary)]">联网检索</span>
        </label>
        <label class="flex items-center gap-2 text-sm cursor-pointer">
          <el-switch v-model="enableTTS" size="small" />
          <span class="text-[var(--text-secondary)]">AI 语音</span>
        </label>
        <label class="flex items-center gap-2 text-sm cursor-pointer">
          <el-switch v-model="enableImageGeneration" size="small" />
          <span class="text-[var(--text-secondary)]">课件插图</span>
        </label>
      </div>

      <!-- 状态提示 -->
      <div v-if="generating" class="flex items-center gap-2 text-sm text-[var(--color-primary)]">
        <el-icon class="is-loading"><Loading /></el-icon>
        正在请求 OpenMAIC 生成课堂，预计需要 2–5 分钟…
      </div>
      <div v-if="error" class="p-3 rounded-lg text-sm bg-[var(--color-error-light)] text-[var(--color-error)] border border-[var(--color-error)]/20">
        {{ error }}
      </div>
    </div>

    <template #footer>
      <div class="flex gap-2">
        <span v-if="generated" class="text-sm text-[var(--color-success)] flex items-center gap-1">
          <el-icon><Check /></el-icon> 已生成
        </span>
        <div class="flex-1" />
        <el-button @click="close">取消</el-button>
        <el-button
          type="primary"
          :disabled="!requirement.trim() || selectedDocs.length === 0 || generating"
          :loading="generating"
          @click="generate"
        >
          {{ generating ? '生成中...' : '生成课堂' }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Loading, Check } from '@/components/icons'
import api from '../../services/api'
import type { Document } from '../../types/models'

const props = withDefaults(defineProps<{
  /** v-model 绑定可见性 */
  modelValue: boolean
  /** 可选：预选文档列表 */
  documents: Document[]
}>(), {
  modelValue: false,
  documents: () => [],
})

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'generated': [result: { jobId: string; courseId?: string }]
  close: []
}>()

// ── 状态 ────────────────────────────────────────────────────────────────────

const localVisible = ref(props.modelValue)
const requirement = ref('')
const selectedDocs = ref<string[]>([])
const enableWebSearch = ref(false)
const enableTTS = ref(true)
const enableImageGeneration = ref(false)
const generating = ref(false)
const error = ref('')
const generated = ref(false)

// ── 监听外部 v-model ─────────────────────────────────────────────────────────

watch(() => props.modelValue, (v) => { localVisible.value = v })
watch(localVisible, (v) => { emit('update:modelValue', v) })

// ── 方法 ─────────────────────────────────────────────────────────────────────

function toggleDoc(docId: string): void {
  const idx = selectedDocs.value.indexOf(docId)
  if (idx >= 0) {
    selectedDocs.value.splice(idx, 1)
  } else if (selectedDocs.value.length < 5) {
    selectedDocs.value.push(docId)
  }
}

async function generate(): Promise<void> {
  if (!requirement.value.trim() || selectedDocs.value.length === 0) return

  generating.value = true
  error.value = ''
  generated.value = false

  try {
    const resp = await api.post('/integrations/openmaic/classroom', {
      doc_ids: selectedDocs.value,
      requirement: requirement.value.trim(),
      enable_web_search: enableWebSearch.value,
      enable_tts: enableTTS.value,
      enable_image_generation: enableImageGeneration.value,
      agent_mode: 'default',
    })
    generated.value = true
    ElMessage.success('课堂生成任务已提交！可以通过 jobId 追踪进度。')
    emit('generated', {
      jobId: resp.data.job_id,
      courseId: resp.data.course_id ?? undefined,
    })
    setTimeout(() => close(), 1500)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '生成失败'
    ElMessage.error(error.value)
  } finally {
    generating.value = false
  }
}

function close(): void {
  localVisible.value = false
  error.value = ''
  generated.value = false
  setTimeout(() => emit('close'), 300)
}

function onClosed(): void {
  // 重置但不 emit close，避免和 v-model 循环
}
</script>
