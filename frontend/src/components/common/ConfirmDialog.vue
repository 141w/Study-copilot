<template>
  <el-dialog
    :model-value="modelValue"
    :title="title"
    width="400px"
    :close-on-click-modal="false"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <p class="text-sm text-[var(--text-secondary)] mb-6">{{ message }}</p>
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button type="danger" :loading="loading" @click="$emit('confirm')">
        {{ confirmText }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
/**
 * ConfirmDialog（P2-2）：统一删除/危险操作确认弹窗。
 *
 * 替代散落在 NotesView / CourseDetailView / CourseListView / UploadView
 * 的 4 份几乎相同的 el-dialog 确认弹窗模板。
 */
withDefaults(defineProps<{
  modelValue: boolean
  title: string
  message: string
  confirmText?: string
  loading?: boolean
}>(), {
  confirmText: '确认',
  loading: false
})

defineEmits<{
  'update:modelValue': [value: boolean]
  confirm: []
}>()
</script>
