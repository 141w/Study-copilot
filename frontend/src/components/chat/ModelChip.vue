<template>
  <el-dropdown trigger="click" @command="onCommand" data-test="model-chip">
    <button
      type="button"
      class="inline-flex items-center gap-1.5 px-2.5 h-8 rounded-full border border-[var(--border-default)] bg-[var(--surface-card)] text-[11px] text-[var(--text-secondary)] hover:border-[var(--border-hover)] transition-colors"
      title="切换模型"
    >
      <span class="max-w-[120px] truncate font-medium text-[var(--text-primary)]">{{ modelName }}</span>
      <span class="tabular-nums text-[10px] text-[var(--text-muted)]">{{ windowHint }}</span>
    </button>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item command="config">模型配置…</el-dropdown-item>
        <el-dropdown-item
          v-for="m in models"
          :key="m.id"
          :command="'pick:' + m.id"
        >
          {{ m.label }}
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore } from '@/stores/chat'

const LS_KEY = 'study-copilot.chat-model'

const props = withDefaults(
  defineProps<{
    models?: { id: string; label: string; contextWindow?: number }[]
  }>(),
  { models: () => [] }
)

const emit = defineEmits<{ (e: 'select', id: string): void }>()
const router = useRouter()
const chatStore = useChatStore()
const selectedId = ref('')

const modelName = computed(() => {
  const fromStore = chatStore.config?.modelName || ''
  const hit = props.models.find(m => m.id === selectedId.value)
  return hit?.label || fromStore || '默认模型'
})

const windowHint = computed(() => {
  const hit = props.models.find(m => m.id === selectedId.value)
  const n = hit?.contextWindow
  if (!n) return ''
  return n >= 1000 ? `${Math.round(n / 1000)}k` : String(n)
})

function onCommand(cmd: string | number | object): void {
  const s = String(cmd)
  if (s === 'config') {
    router.push('/model-config')
    return
  }
  if (s.startsWith('pick:')) {
    const id = s.slice(5)
    selectedId.value = id
    try {
      localStorage.setItem(LS_KEY, id)
    } catch { /* ignore */ }
    emit('select', id)
  }
}

onMounted(() => {
  try {
    const saved = localStorage.getItem(LS_KEY)
    if (saved) selectedId.value = saved
  } catch { /* ignore */ }
})
</script>
