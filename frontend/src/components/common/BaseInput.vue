<template>
  <div class="base-input-wrapper">
    <label v-if="label" :for="inputId" class="base-input-label">
      {{ label }}
      <span v-if="required" class="text-[var(--color-error)]">*</span>
    </label>
    <div class="relative">
      <input
        :id="inputId"
        ref="inputRef"
        :type="type"
        :value="modelValue"
        :placeholder="placeholder"
        :disabled="disabled"
        :readonly="readonly"
        :class="[
          'base-input',
          { 'base-input-error': error },
          { 'base-input-disabled': disabled }
        ]"
        @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
        @blur="$emit('blur', $event)"
        @focus="$emit('focus', $event)"
      />
      <div v-if="$slots.suffix" class="absolute right-3 top-1/2 -translate-y-1/2">
        <slot name="suffix" />
      </div>
    </div>
    <p v-if="error" class="base-input-error-message">{{ error }}</p>
    <p v-else-if="hint" class="base-input-hint">{{ hint }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

interface Props {
  modelValue?: string | number
  type?: string
  label?: string
  placeholder?: string
  disabled?: boolean
  readonly?: boolean
  required?: boolean
  error?: string
  hint?: string
}

const props = withDefaults(defineProps<Props>(), {
  type: 'text',
  disabled: false,
  readonly: false,
  required: false
})

defineEmits<{
  'update:modelValue': [value: string]
  'blur': [event: FocusEvent]
  'focus': [event: FocusEvent]
}>()

const inputRef = ref<HTMLInputElement | null>(null)
const inputId = computed(() => `input-${Math.random().toString(36).slice(2, 9)}`)

function focus() {
  inputRef.value?.focus()
}

defineExpose({ focus, inputRef })
</script>

<style scoped>
.base-input-wrapper {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.base-input-label {
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--text-secondary);
}

.base-input {
  width: 100%;
  padding: var(--spacing-sm) var(--spacing-md);
  font-size: var(--font-size-sm);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  background-color: var(--bg-primary);
  color: var(--text-primary);
  outline: none;
  transition: all var(--transition-fast);
}

.base-input::placeholder {
  color: var(--text-muted);
}

.base-input:focus {
  border-color: var(--border-focus);
  box-shadow: 0 0 0 2px var(--color-primary-light);
}

.base-input-error {
  border-color: var(--color-error);
}

.base-input-error:focus {
  box-shadow: 0 0 0 2px var(--color-error-light);
}

.base-input-disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.base-input-error-message {
  font-size: var(--font-size-xs);
  color: var(--color-error);
}

.base-input-hint {
  font-size: var(--font-size-xs);
  color: var(--text-muted);
}
</style>
