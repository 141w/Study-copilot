<template>
  <div class="base-select-wrapper">
    <label v-if="label" :for="selectId" class="base-select-label">
      {{ label }}
      <span v-if="required" class="text-[var(--color-error)]">*</span>
    </label>
    <select
      :id="selectId"
      :value="modelValue"
      :disabled="disabled"
      :class="[
        'base-select',
        { 'base-select-error': error },
        { 'base-select-disabled': disabled }
      ]"
      @change="$emit('update:modelValue', ($event.target as HTMLSelectElement).value)"
    >
      <option v-if="placeholder" value="" disabled>{{ placeholder }}</option>
      <option
        v-for="option in options"
        :key="option.value"
        :value="option.value"
      >
        {{ option.label }}
      </option>
    </select>
    <p v-if="error" class="base-select-error-message">{{ error }}</p>
    <p v-else-if="hint" class="base-select-hint">{{ hint }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface SelectOption {
  value: string | number
  label: string
}

interface Props {
  modelValue?: string | number
  options: SelectOption[]
  label?: string
  placeholder?: string
  disabled?: boolean
  required?: boolean
  error?: string
  hint?: string
}

withDefaults(defineProps<Props>(), {
  disabled: false,
  required: false
})

defineEmits<{
  'update:modelValue': [value: string]
}>()

const selectId = computed(() => `select-${Math.random().toString(36).slice(2, 9)}`)
</script>

<style scoped>
.base-select-wrapper {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.base-select-label {
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--text-secondary);
}

.base-select {
  width: 100%;
  padding: var(--spacing-sm) var(--spacing-md);
  font-size: var(--font-size-sm);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  background-color: var(--bg-primary);
  color: var(--text-primary);
  outline: none;
  transition: all var(--transition-fast);
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e");
  background-position: right 0.5rem center;
  background-repeat: no-repeat;
  background-size: 1.5em 1.5em;
  padding-right: 2.5rem;
}

.base-select:focus {
  border-color: var(--border-focus);
  box-shadow: 0 0 0 2px var(--color-primary-light);
}

.base-select-error {
  border-color: var(--color-error);
}

.base-select-error:focus {
  box-shadow: 0 0 0 2px var(--color-error-light);
}

.base-select-disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.base-select-error-message {
  font-size: var(--font-size-xs);
  color: var(--color-error);
}

.base-select-hint {
  font-size: var(--font-size-xs);
  color: var(--text-muted);
}
</style>
