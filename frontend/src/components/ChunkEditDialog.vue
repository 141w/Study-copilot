<template>
  <el-dialog
    v-model="visible"
    title="编辑切片"
    width="min(720px, 96vw)"
    destroy-on-close
    @closed="reset"
  >
    <div class="space-y-3">
      <label class="block text-xs font-medium text-[var(--text-secondary)]">切片正文</label>
      <el-input
        v-model="draft"
        type="textarea"
        :rows="10"
        :maxlength="50000"
        placeholder="编辑切片内容…"
        data-test="chunk-edit-input"
      />

      <p v-if="conflictError" class="text-sm text-[var(--color-error)]" data-test="edit-conflict">
        {{ conflictError }}
      </p>
      <p v-else-if="error" class="text-sm text-[var(--color-error)]" data-test="edit-error">
        {{ error }}
      </p>

      <!-- 索引状态三态：处理中 / 就绪 / 失败+重试 -->
      <div
        v-if="indexStatus"
        class="flex items-center gap-2 text-sm rounded-lg px-3 py-2 border"
        data-test="index-status"
      >
        <template v-if="indexStatus === 'processing'">
          <el-icon class="is-loading text-[var(--color-warning)]"><Loading /></el-icon>
          <span data-test="status-processing" class="text-[var(--color-warning)]">索引处理中…</span>
        </template>
        <template v-else-if="indexStatus === 'ready'">
          <el-icon class="text-[var(--color-success)]"><CircleCheckFilled /></el-icon>
          <span data-test="status-ready" class="text-[var(--color-success)]">索引已就绪</span>
        </template>
        <template v-else-if="indexStatus === 'failed'">
          <el-icon class="text-[var(--color-error)]"><CircleCloseFilled /></el-icon>
          <span data-test="status-failed" class="text-[var(--color-error)]">索引失败</span>
          <el-button
            size="small"
            type="danger"
            data-test="retry-index"
            :loading="saving"
            :disabled="saving"
            @click="save"
          >
            重试
          </el-button>
        </template>
      </div>
    </div>

    <template #footer>
      <div class="flex justify-end gap-2">
        <el-button @click="close">取消</el-button>
        <el-button type="primary" :loading="saving" data-test="save-chunk" @click="save">
          保存
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { CircleCheckFilled, CircleCloseFilled, Loading } from '@/components/icons'
import api from '@/services/api'

export interface ChunkEditTarget {
  id: string
  content: string
  contentRevision: number
}

const props = defineProps<{
  visible: boolean
  docId: string
  chunk: ChunkEditTarget | null
}>()
const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'saved', payload: { id: string; content: string; contentRevision: number; indexStatus: string }): void
}>()

const visible = computed({
  get: () => props.visible,
  set: (v: boolean) => emit('update:visible', v),
})

const draft = ref('')
const expectedRevision = ref(0)
const saving = ref(false)
const error = ref('')
const conflictError = ref('')
const indexStatus = ref<'' | 'processing' | 'ready' | 'failed'>('')

watch(
  () => props.chunk,
  (c) => {
    if (c) {
      draft.value = c.content
      expectedRevision.value = c.contentRevision
      indexStatus.value = ''
      error.value = ''
      conflictError.value = ''
    }
  },
  { immediate: true },
)

function reset(): void {
  draft.value = ''
  error.value = ''
  conflictError.value = ''
  indexStatus.value = ''
}

function close(): void {
  visible.value = false
}

async function save(): Promise<void> {
  if (!props.chunk || !props.docId) return
  saving.value = true
  error.value = ''
  conflictError.value = ''
  try {
    const res = await api.put(`/documents/${props.docId}/chunks/${props.chunk.id}`, {
      content: draft.value,
      expected_revision: expectedRevision.value,
    })
    const data = res.data as {
      content: string
      content_revision: number
      index_status: string
      error?: string
    }
    expectedRevision.value = data.content_revision
    indexStatus.value = (data.index_status as 'processing' | 'ready' | 'failed') || ''
    if (data.index_status === 'failed') {
      error.value = data.error || '重嵌入失败，可点击重试'
    }
    emit('saved', {
      id: props.chunk.id,
      content: data.content,
      contentRevision: data.content_revision,
      indexStatus: data.index_status,
    })
  } catch (e: unknown) {
    const err = e as { response?: { status?: number; data?: { detail?: string } } }
    if (err.response?.status === 409) {
      conflictError.value = err.response.data?.detail || '版本冲突：他人已修改该切片，请刷新后重试'
    } else {
      error.value = err.response?.data?.detail || '保存失败'
    }
  } finally {
    saving.value = false
  }
}
</script>
