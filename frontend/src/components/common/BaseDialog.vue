<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="visible"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
        @click.self="handleBackdropClick"
      >
        <div
          class="bg-white rounded-xl shadow-xl overflow-hidden"
          :class="sizeClass"
        >
          <!-- Header -->
          <div class="px-6 py-4 border-b border-[var(--border-default)] flex items-center justify-between">
            <h3 class="text-lg font-semibold text-[var(--text-primary)]">
              <slot name="header">{{ title }}</slot>
            </h3>
            <button
              @click="close"
              class="text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <!-- Body -->
          <div class="p-6">
            <slot />
          </div>

          <!-- Footer -->
          <div
            v-if="$slots.footer"
            class="px-6 py-4 border-t border-[var(--border-default)] flex items-center justify-between bg-[var(--bg-secondary)]"
          >
            <slot name="footer-left" />
            <div class="flex gap-2">
              <slot name="footer" />
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    default: ''
  },
  size: {
    type: String,
    default: 'md',
    validator: (value) => ['sm', 'md', 'lg', 'xl'].includes(value)
  },
  closeOnBackdrop: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['update:visible', 'close'])

const sizeClass = computed(() => {
  const sizes = {
    sm: 'w-full max-w-sm mx-4',
    md: 'w-full max-w-md mx-4',
    lg: 'w-full max-w-lg mx-4',
    xl: 'w-full max-w-xl mx-4'
  }
  return sizes[props.size] || sizes.md
})

function handleBackdropClick() {
  if (props.closeOnBackdrop) {
    close()
  }
}

function close() {
  emit('update:visible', false)
  emit('close')
}
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
