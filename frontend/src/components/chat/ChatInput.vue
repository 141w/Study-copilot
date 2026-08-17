<template>
  <div class="border-t border-gray-100 bg-white p-4">
    <div class="flex gap-3 max-w-4xl mx-auto">
      <input
        v-model="inputText"
        type="text"
        placeholder="输入您的问题..."
        class="flex-1 px-4 py-3 border border-gray-200 rounded-lg focus:outline-none focus:border-[#010120] focus:ring-1 focus:ring-[#010120] transition-all"
        @keydown.enter="sendMessage"
        :disabled="disabled"
      />
      <button
        v-if="loading"
        @click="stopStream"
        class="px-6 py-3 bg-red-500 text-white rounded-lg font-medium transition-all hover:bg-red-600"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
      <button
        v-else
        @click="sendMessage"
        :disabled="disabled || !inputText.trim()"
        class="px-6 py-3 bg-[#010120] text-white rounded-lg font-medium transition-all hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

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