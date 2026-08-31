<template>
  <div class="border-t border-[var(--border-default)] bg-[var(--bg-primary)] p-4">
    <div class="flex gap-3 max-w-4xl mx-auto">
      <el-input
        v-model="inputText"
        placeholder="输入您的问题..."
        class="flex-1"
        :disabled="disabled"
        @keydown.enter="sendMessage"
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

<script setup>
import { ref } from 'vue'
import { Close, Promotion } from '@element-plus/icons-vue'

const props = defineProps({
  loading: Boolean,
  disabled: Boolean
})

const emit = defineEmits(['send', 'stop'])

const inputText = ref('')

function sendMessage() {
  if (inputText.value.trim() && !props.disabled) {
    emit('send', inputText.value.trim())
    inputText.value = ''
  }
}

function stopStream() {
  emit('stop')
}
</script>
