<template>
  <button
    :type="type"
    :disabled="disabled || loading"
    :class="[variantClass, sizeClass, { 'opacity-50 cursor-not-allowed': disabled || loading }]"
    class="inline-flex items-center justify-center gap-2 transition-all"
    @click="$emit('click', $event)"
  >
    <LoadingSpinner v-if="loading" :size="spinnerSize" />
    <slot />
  </button>
</template>

<script setup>
import { computed } from 'vue'
import LoadingSpinner from './LoadingSpinner.vue'

const props = defineProps({
  variant: {
    type: String,
    default: 'primary',
    validator: (value) => ['primary', 'secondary', 'ghost', 'danger'].includes(value)
  },
  size: {
    type: String,
    default: 'md',
    validator: (value) => ['sm', 'md', 'lg'].includes(value)
  },
  type: {
    type: String,
    default: 'button'
  },
  disabled: {
    type: Boolean,
    default: false
  },
  loading: {
    type: Boolean,
    default: false
  }
})

defineEmits(['click'])

const variantClass = computed(() => {
  const variants = {
    primary: 'bg-[#010120] text-white rounded-lg hover:opacity-90',
    secondary: 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors',
    ghost: 'text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors',
    danger: 'bg-red-600 text-white rounded-lg hover:bg-red-700'
  }
  return variants[props.variant] || variants.primary
})

const sizeClass = computed(() => {
  const sizes = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-4 py-2 text-sm',
    lg: 'px-6 py-3 text-base'
  }
  return sizes[props.size] || sizes.md
})

const spinnerSize = computed(() => {
  const sizes = {
    sm: 'xs',
    md: 'sm',
    lg: 'md'
  }
  return sizes[props.size] || 'sm'
})
</script>
