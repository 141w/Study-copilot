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
        @click="sendMessage"
        :disabled="disabled || !inputText.trim()"
        class="px-6 py-3 bg-[#010120] text-white rounded-lg font-medium transition-all hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <svg v-if="!loading" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
        </svg>
        <svg v-else class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
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

const emit = defineEmits(['send'])

const inputText = ref('')

function sendMessage() {
  if (inputText.value.trim() && !props.disabled) {
    emit('send', inputText.value.trim())
    inputText.value = ''
  }
}
</script>