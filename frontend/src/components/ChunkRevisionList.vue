<template>
  <el-dialog
    v-model="visible"
    title="版本历史"
    width="min(720px, 96vw)"
    destroy-on-close
    @opened="load"
    @closed="reset"
  >
    <div class="space-y-3">
      <p v-if="loading" class="text-sm text-[var(--text-muted)]">加载中…</p>
      <p v-else-if="error" class="text-sm text-[var(--color-error)]" data-test="revision-error">
        {{ error }}
      </p>
      <p v-else-if="revisions.length === 0" class="text-sm text-[var(--text-muted)]" data-test="revision-empty">
        暂无历史版本（首次编辑后生成快照）
      </p>
      <div v-else class="space-y-2 max-h-[60vh] overflow-y-auto">
        <div
          v-for="rev in revisions"
          :key="rev.id"
          class="card !p-3 !rounded-lg"
          data-test="revision-item"
        >
          <div class="flex items-center justify-between text-xs text-[var(--text-muted)] mb-1">
            <span>revision {{ rev.revision }}</span>
            <span>{{ rev.edited_at }}</span>
          </div>
          <p class="text-sm text-[var(--text-secondary)] whitespace-pre-wrap line-clamp-4 mb-2">
            {{ rev.content }}
          </p>
          <el-button
            size="small"
            type="primary"
            data-test="revert-btn"
            :loading="revertingId === rev.id"
            @click="revert(rev)"
          >
            回滚到此版本
          </el-button>
        </div>
      </div>
      <p v-if="revertError" class="text-sm text-[var(--color-error)]" data-test="revert-error">
        {{ revertError }}
      </p>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import api from '@/services/api'

export interface ChunkRevisionItem {
  id: string
  revision: number
  content: string
  editor_id?: string | null
  edited_at?: string
  is_enabled?: boolean
}

const props = defineProps<{
  visible: boolean
  docId: string
  chunkId: string
  /** 当前 content_revision，用于回滚时的乐观并发校验 */
  contentRevision?: number
}>()
const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'reverted', payload: { content: string; contentRevision: number; indexStatus: string }): void
}>()

const visible = computed({
  get: () => props.visible,
  set: (v: boolean) => emit('update:visible', v),
})

const revisions = ref<ChunkRevisionItem[]>([])
const loading = ref(false)
const error = ref('')
const revertError = ref('')
const revertingId = ref('')

function reset(): void {
  revisions.value = []
  error.value = ''
  revertError.value = ''
  revertingId.value = ''
}

watch(
  () => props.visible,
  (v) => {
    if (v) load()
  },
  { immediate: true },
)

async function load(): Promise<void> {
  if (!props.docId || !props.chunkId) return
  loading.value = true
  error.value = ''
  try {
    const res = await api.get(`/documents/${props.docId}/chunks/${props.chunkId}/revisions`)
    revisions.value = (res.data as ChunkRevisionItem[]) || []
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail || '加载版本历史失败'
  } finally {
    loading.value = false
  }
}

async function revert(rev: ChunkRevisionItem): Promise<void> {
  if (!props.docId || !props.chunkId) return
  revertingId.value = rev.id
  revertError.value = ''
  try {
    const res = await api.post(`/documents/${props.docId}/chunks/${props.chunkId}/revert`, {
      revision: rev.revision,
      // 回滚=一次编辑：带上当前 revision 做乐观并发，避免静默覆盖
      ...(props.contentRevision !== undefined
        ? { expected_revision: props.contentRevision }
        : {}),
    })
    const data = res.data as { content: string; content_revision: number; index_status: string }
    emit('reverted', {
      content: data.content,
      contentRevision: data.content_revision,
      indexStatus: data.index_status,
    })
    visible.value = false
  } catch (e: unknown) {
    const err = e as { response?: { status?: number; data?: { detail?: string } } }
    if (err.response?.status === 409) {
      revertError.value = '版本已变化，请刷新后重试'
    } else {
      revertError.value = err.response?.data?.detail || '回滚失败'
    }
  } finally {
    revertingId.value = ''
  }
}

defineExpose({ load, revert, revisions })
</script>
