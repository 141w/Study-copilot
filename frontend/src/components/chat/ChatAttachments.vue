<template>
  <div
    v-if="attachments.length"
    class="chat-attachments flex flex-wrap gap-1.5 mb-1.5"
    data-test="chat-attachments"
  >
    <div
      v-for="att in attachments"
      :key="att.id"
      class="attachment-chip group flex items-center gap-1.5 max-w-[220px] rounded-md border border-[var(--border-default)] bg-[var(--surface-card)] px-2 py-1 text-xs"
      :data-test="`attachment-${att.id}`"
      :data-status="att.status"
    >
      <el-icon :size="13" class="shrink-0 text-[var(--text-secondary)]">
        <component :is="att.file_type === 'image' ? View : Document" />
      </el-icon>
      <span class="truncate text-[var(--text-primary)]" :title="att.filename">{{ att.filename }}</span>

      <!-- 两阶段状态：上传中禁发；解析中/就绪可发 -->
      <span
        class="shrink-0 rounded px-1 py-0.5 text-[10px] leading-none font-medium"
        :class="statusClass(att.status)"
        data-test="attachment-status"
      >
        {{ statusLabel(att.status) }}
      </span>

      <button
        type="button"
        class="shrink-0 opacity-50 hover:opacity-100 text-[var(--text-muted)] hover:text-[var(--color-error)] transition-opacity"
        :aria-label="`移除附件 ${att.filename}`"
        data-test="attachment-remove"
        @click="$emit('remove', att.id)"
      >
        <el-icon :size="12"><Close /></el-icon>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Close, Document, View } from '@/components/icons'

export interface ChatAttachmentItem {
  id: string
  filename: string
  file_type: 'image' | 'document'
  /** uploading(客户端) | uploaded | parsing | ready | error */
  status: string
  size?: number
}

defineProps<{
  attachments: ChatAttachmentItem[]
}>()

defineEmits<{
  remove: [id: string]
}>()

function statusLabel(status: string): string {
  switch (status) {
    case 'uploading':
      return '上传中'
    case 'uploaded':
      return '就绪' // 图片上传完成即可发
    case 'parsing':
      return '解析中'
    case 'ready':
      return '就绪'
    case 'error':
      return '失败'
    default:
      return status
  }
}

function statusClass(status: string): string {
  switch (status) {
    case 'uploading':
      return 'bg-[var(--color-primary)]/10 text-[var(--color-primary)]'
    case 'parsing':
      return 'bg-[var(--color-warning,#f59e0b)]/10 text-[var(--color-warning,#f59e0b)]'
    case 'uploaded':
    case 'ready':
      return 'bg-[var(--color-success,#10b981)]/10 text-[var(--color-success,#10b981)]'
    case 'error':
      return 'bg-[var(--color-error)]/10 text-[var(--color-error)]'
    default:
      return 'bg-[var(--text-muted)]/10 text-[var(--text-muted)]'
  }
}
</script>
