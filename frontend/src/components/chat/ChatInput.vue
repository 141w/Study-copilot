<template>
  <div class="border-t border-[var(--border-default)] bg-[var(--bg-primary)] p-4">
    <div class="flex gap-3 max-w-4xl mx-auto">
      <el-input
        v-model="inputText"
        :placeholder="placeholder"
        class="flex-1"
        :disabled="disabled"
        @keydown.enter="handleEnter"
      />
      <el-button
        v-if="loading"
        type="danger"
        :icon="Close"
        @click="stopStream"
      />
      <el-button
        v-else
        type="primary"
        :icon="Promotion"
        :disabled="disabled || !inputText.trim()"
        @click="sendMessage"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Close, Promotion } from '@element-plus/icons-vue'

const props = withDefaults(defineProps<{
  loading?: boolean
  disabled?: boolean
  placeholder?: string
}>(), {
  loading: false,
  disabled: false,
  placeholder: '输入您的问题...'
})

const emit = defineEmits<{
  send: [content: string]
  stop: []
}>()

const inputText = ref('')

function handleEnter(event: Event | KeyboardEvent): void {
  // isComposing 为 true 表示输入法组合中（中文输入选词阶段的回车不发送）；
  // 模板事件签名是联合类型，收窄后取 isComposing
  const ke = event as KeyboardEvent
  if (ke.isComposing) return
  sendMessage()
}

function sendMessage(): void {
  if (inputText.value.trim() && !props.disabled) {
    emit('send', inputText.value.trim())
    inputText.value = ''
  }
}

function stopStream(): void {
  emit('stop')
}
</script>
