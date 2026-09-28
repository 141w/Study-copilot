<template>
  <div class="space-y-2">
    <div class="flex items-center gap-2">
      <button
        type="button"
        class="px-2 py-1 text-xs rounded-md border transition-colors cursor-pointer"
        :class="selectMode
          ? 'border-[var(--color-primary)] text-[var(--color-primary)] bg-[var(--color-primary)]/10'
          : 'border-[var(--border-default)] text-[var(--text-secondary)]'"
        data-test="doc-batch-toggle"
        @click="toggleSelectMode"
      >
        {{ selectMode ? `已选 ${selected.length}` : '批量' }}
      </button>
      <template v-if="selectMode">
        <el-button size="small" :disabled="selected.length === 0" @click="openTagDialog">
          打标签
        </el-button>
        <el-button size="small" :disabled="selected.length === 0" :loading="autoTagging" @click="runAutoTag">
          自动打标
        </el-button>
        <el-button size="small" text @click="clearSelection">取消</el-button>
      </template>
    </div>

    <el-dialog v-model="tagDialogOpen" title="批量打标签" width="420px">
      <p class="text-xs text-[var(--text-muted)] mb-3">
        为 {{ selected.length }} 篇文档添加标签（已有标签不会被删除）。
      </p>
      <el-input
        v-model="tagInput"
        placeholder="标签，逗号分隔，如 机器学习,重点"
        data-test="batch-tag-input"
        @keyup.enter="applyBatchTag"
      />
      <template #footer>
        <el-button @click="tagDialogOpen = false">取消</el-button>
        <el-button type="primary" :loading="tagging" data-test="batch-tag-confirm" @click="applyBatchTag">
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../services/api'

const props = defineProps<{ selected: string[]; selectMode: boolean }>()
const emit = defineEmits<{
  (e: 'update:selectMode', v: boolean): void
  (e: 'update:selected', v: string[]): void
  (e: 'done'): void
}>()

const tagDialogOpen = ref(false)
const tagInput = ref('')
const tagging = ref(false)
const autoTagging = ref(false)

function toggleSelectMode(): void {
  emit('update:selectMode', !props.selectMode)
  if (props.selectMode) emit('update:selected', [])
}

function clearSelection(): void {
  emit('update:selected', [])
  emit('update:selectMode', false)
}

function openTagDialog(): void {
  tagInput.value = ''
  tagDialogOpen.value = true
}

async function applyBatchTag(): Promise<void> {
  const names = tagInput.value
    .split(/[,，、]/)
    .map(s => s.trim())
    .filter(Boolean)
  if (!names.length) {
    ElMessage.warning('请输入至少一个标签')
    return
  }
  tagging.value = true
  try {
    await api.post('/documents/batch-tag', {
      document_ids: props.selected,
      tag_names: names
    })
    ElMessage.success('已打标签')
    tagDialogOpen.value = false
    emit('done')
    clearSelection()
  } catch {
    ElMessage.error('批量打标签失败')
  } finally {
    tagging.value = false
  }
}

async function runAutoTag(): Promise<void> {
  autoTagging.value = true
  try {
    const { data } = await api.post('/documents/batch-auto-tag', {
      document_ids: props.selected,
      tag_names: []
    })
    const added = Object.values((data as { results: Record<string, string[]> })?.results || {})
      .reduce((n, arr) => n + (arr?.length || 0), 0)
    ElMessage.success(added ? `自动打上 ${added} 个标签` : '未匹配到合适标签')
    emit('done')
    clearSelection()
  } catch {
    ElMessage.error('自动打标失败')
  } finally {
    autoTagging.value = false
  }
}
</script>
