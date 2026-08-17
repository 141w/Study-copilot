<template>
  <div class="base-textarea-wrapper">
    <label v-if="label" :for="textareaId" class="base-textarea-label">
      {{ label }}
      <span v-if="required" class="text-[var(--color-error)]">*</span>
    </label>
    <textarea
      :id="textareaId"
      ref="textareaRef"
      :value="modelValue"
      :placeholder="placeholder"
      :disabled="disabled"
      :readonly="readonly"
      :rows="rows"
      :maxlength="maxlength"
      :class="[
        'base-textarea',
        { 'base-textarea-error': error },
        { 'base-textarea-disabled': disabled }
      ]"
      @input="$emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
      @blur="$emit('blur', $event)"
      @focus="$emit('focus', $event)"
    />
    <div v-if="maxlength" class="flex justify-end">
      <span class="base-textarea-count">
        {{ (modelValue as string)?.length || 0 }}/{{ maxlength }}
      </span>
    </div>
    <p v-if="error" class="base-textarea-error-message">{{ error }}</p>
    <p v-else-if="hint" class="base-textarea-hint">{{ hint }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

interface Props {
  modelValue?: string
  label?: string
  placeholder?: string
  disabled?: boolean
  readonly?: boolean
  required?: boolean
  rows?: number
  maxlength?: number
  error?: string
  hint?: string
}

withDefaults(defineProps<Props>(), {
  disabled: false,
  readonly: false,
  required: false,
  rows: 4
})

defineEmits<{
  'update:modelValue': [value: string]
  'blur': [event: FocusEvent]
  'focus': [event: FocusEvent]
}>()

const textareaRef = ref<HTMLTextAreaElement | null>(null)
const textareaId = computed(() => `textarea-${Math.random().toString(36).slice(2, 9)}`)

function focus() {
  textareaRef.value?.focus()
}

defineExpose({ focus, textareaRef })
</script>

<style scoped>
.base-textarea-wrapper {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.base-textarea-label {
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--text-secondary);
}

.base-textarea {
  width: 100%;
  padding: var(--spacing-sm) var(--spacing-md);
  font-size: var(--font-size-sm);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  background-color: var(--bg-primary);
  color: var(--text-primary);
  outline: none;
  transition: all var(--transition-fast);
  resize: vertical;
  min-height: 80px;
}

.base-textarea::placeholder {
  color: var(--text-muted);
}

.base-textarea:focus {
  border-color: var(--border-focus);
  box-shadow: 0 0 0 2px var(--color-primary-light);
}

.base-textarea-error {
  border-color: var(--color-error);
}

.base-textarea-error:focus {
  box-shadow: 0 0 0 2px var(--color-error-light);
}

.base-textarea-disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.base-textarea-count {
  font-size: var(--font-size-xs);
  color: var(--text-muted);
}

.base-textarea-error-message {
  font-size: var(--font-size-xs);
  color: var(--color-error);
}

.base-textarea-hint {
  font-size: var(--font-size-xs);
  color: var(--text-muted);
}
</style>
