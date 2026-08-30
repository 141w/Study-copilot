<template>
  <button
    :class="[sizeClass, variantClass]"
    class="inline-flex items-center justify-center transition-colors"
    @click="$emit('click', $event)"
  >
    <slot />
  </button>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  size: {
    type: String,
    default: 'md',
    validator: (value) => ['xs', 'sm', 'md', 'lg'].includes(value)
  },
  variant: {
    type: String,
    default: 'ghost',
    validator: (value) => ['ghost', 'primary', 'danger'].includes(value)
  }
})

defineEmits(['click'])

const sizeClass = computed(() => {
  const sizes = {
    xs: 'w-6 h-6',
    sm: 'w-8 h-8',
    md: 'w-10 h-10',
    lg: 'w-12 h-12'
  }
  return sizes[props.size] || sizes.md
})

const variantClass = computed(() => {
  const variants = {
    ghost: 'text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] rounded-lg',
    primary: 'text-[#010120] hover:bg-[var(--bg-tertiary)] rounded-lg',
    danger: 'text-red-500 hover:text-red-700 hover:bg-red-50 rounded-lg'
  }
  return variants[props.variant] || variants.ghost
})
</script>
