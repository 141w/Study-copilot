<template>
  <div class="model-display relative inline-block select-none" data-test="model-chip">
    <!-- 胶囊触发按钮 (参照 WeKnora model-selector-trigger 规范) -->
    <div
      ref="triggerRef"
      class="model-selector-trigger"
      :class="{ 'is-active': dropdownVisible, 'is-empty': isEmpty }"
      title="切换当前对话模型"
      @click.stop="toggleDropdown"
    >
      <span class="model-icon">
        <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 01-6.23-.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L4.2 15.3" />
        </svg>
      </span>
      <span class="model-selector-name">{{ currentModelName }}</span>
      <span v-if="currentContextLabel" class="model-selector-ctx">{{ currentContextLabel }}</span>
      <svg
        class="model-dropdown-arrow w-2.5 h-2.5 transition-transform duration-200"
        :class="{ 'rotate-180': dropdownVisible }"
        viewBox="0 0 12 12"
        fill="currentColor"
      >
        <path d="M2.5 4.5L6 8L9.5 4.5H2.5Z" />
      </svg>
    </div>

    <!-- 弹层菜单 (Teleport 到 body，精确跟随锚点，参照 WeKnora model-selector-dropdown 规范) -->
    <Teleport to="body">
      <div
        v-if="dropdownVisible"
        class="model-selector-overlay fixed inset-0 z-[9998] bg-transparent"
        @click="closeDropdown"
      >
        <div
          class="model-selector-dropdown fixed z-[9999]"
          :style="dropdownStyle"
          @click.stop
        >
          <div class="model-selector-header">
            <span class="font-medium text-[var(--text-secondary)]">对话模型</span>
            <button
              type="button"
              class="model-selector-add"
              @click="goToConfig"
            >
              <span class="text-xs">配置模型</span>
              <svg class="w-3 h-3 ml-0.5" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clip-rule="evenodd" />
              </svg>
            </button>
          </div>

          <div class="model-selector-content max-h-64 overflow-y-auto py-1">
            <div
              v-for="item in computedModels"
              :key="item.id"
              class="model-option"
              :class="{ 'is-selected': item.id === activeModelId }"
              @click="selectModel(item.id)"
            >
              <div class="model-option-left">
                <div class="model-option-icon">
                  <svg class="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
                    <path d="M10 2a6 6 0 00-6 6v3.586l-.707.707A1 1 0 004 14h12a1 1 0 00.707-1.707L16 11.586V8a6 6 0 00-6-6zM10 18a3 3 0 01-3-3h6a3 3 0 01-3 3z" />
                  </svg>
                </div>
                <div class="model-option-name-wrap">
                  <span class="model-option-name">{{ item.label }}</span>
                  <span v-if="item.id !== item.label" class="model-option-raw-name">{{ item.id }}</span>
                </div>
              </div>
              <div class="flex items-center gap-1.5 shrink-0">
                <span v-if="item.contextLabel" class="model-option-ctx">{{ item.contextLabel }}</span>
                <span v-if="item.id === activeModelId" class="text-[var(--color-primary)] font-bold text-xs">✓</span>
              </div>
            </div>

            <div v-if="isEmpty" class="model-selector-empty px-3 py-4 text-center" @click.stop="goToConfig">
              <p class="text-xs text-[var(--text-secondary)]">未检测到已配置的模型</p>
              <p class="text-[11px] text-[var(--text-muted)] mt-1">
                请先在「模型配置」中填写服务商与模型名，此处只列出配置页真实存在的模型
              </p>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useConfigStore } from '@/stores/config'

export interface ModelOptionItem {
  id: string
  label: string
  contextWindow?: number
  contextLabel?: string
}

const LS_KEY = 'study-copilot.chat-model'

const emit = defineEmits<{ (e: 'select', id: string): void }>()
const router = useRouter()
const configStore = useConfigStore()

const triggerRef = ref<HTMLElement | null>(null)
const dropdownVisible = ref(false)
const dropdownStyle = ref<Record<string, string>>({})
const activeModelId = ref<string>('')
/**
 * 配置页真实存在的对话模型。
 * 唯一事实源是服务端 GET /config/llm（单条主配置），
 * 因此可选项数量恒为 0 或 1——不再注入任何预设/默认模型。
 */
const configuredModel = ref<{ name: string; contextWindow?: number } | null>(null)

// 格式化上下文窗口数字（如 131072 -> 128k, 200000 -> 200k）
function formatCtx(num?: number): string {
  if (!num || num <= 0) return ''
  if (num >= 1048576) {
    return `${(num / 1048576).toFixed(1).replace(/\.0$/, '')}M`
  }
  if (num >= 1000) {
    return `${Math.round(num / 1024)}K`
  }
  return String(num)
}

// 模型列表：严格等于配置页真实存在的模型，未配置则为空数组
const computedModels = computed<ModelOptionItem[]>(() => {
  const m = configuredModel.value
  if (!m?.name) return []
  return [{
    id: m.name,
    label: m.name,
    contextWindow: m.contextWindow,
    contextLabel: formatCtx(m.contextWindow),
  }]
})

const isEmpty = computed(() => computedModels.value.length === 0)

const currentModelName = computed(() => computedModels.value[0]?.label || '未配置模型')

const currentContextLabel = computed(() => computedModels.value[0]?.contextLabel || '')

function updateDropdownPos(): void {
  if (!triggerRef.value) return
  const rect = triggerRef.value.getBoundingClientRect()
  const width = 240
  // 向上或向下展开（如果在输入框内部底部，向上展开体验更好）
  const spaceBelow = window.innerHeight - rect.bottom
  const showAbove = spaceBelow < 280

  dropdownStyle.value = {
    minWidth: `${width}px`,
    left: `${Math.max(12, Math.min(rect.left, window.innerWidth - width - 12))}px`,
    top: showAbove ? 'auto' : `${rect.bottom + 6}px`,
    bottom: showAbove ? `${window.innerHeight - rect.top + 6}px` : 'auto',
  }
}

function toggleDropdown(): void {
  dropdownVisible.value = !dropdownVisible.value
  if (dropdownVisible.value) {
    nextTick(updateDropdownPos)
  }
}

function closeDropdown(): void {
  dropdownVisible.value = false
}

function selectModel(id: string): void {
  activeModelId.value = id
  try {
    localStorage.setItem(LS_KEY, id)
  } catch { /* ignore */ }
  dropdownVisible.value = false
  emit('select', id)
}

function goToConfig(): void {
  dropdownVisible.value = false
  router.push('/model-config')
}

onMounted(async () => {
  // 唯一事实源：服务端 GET /config/llm
  const cfg = await configStore.fetchLLMConfig().catch(() => null)
  const name = cfg?.model_name?.trim() || ''
  configuredModel.value = name ? { name, contextWindow: cfg?.context_window } : null

  let saved = ''
  try { saved = localStorage.getItem(LS_KEY) || '' } catch { /* ignore */ }

  if (!name) {
    // 未配置：清空选中与本地残留，触发按钮走「未配置模型」空态
    activeModelId.value = ''
    try { localStorage.removeItem(LS_KEY) } catch { /* ignore */ }
    return
  }

  // 本地记录只有仍等于真实配置时才沿用，
  // 否则一律回落到真实配置——避免显示配置页已改名/已删除的模型
  activeModelId.value = (saved && saved === name) ? saved : name
  try { localStorage.setItem(LS_KEY, activeModelId.value) } catch { /* ignore */ }
})
</script>

<style scoped>
/* 参照 WeKnora model-selector-trigger 规范样式 */
.model-selector-trigger {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 26px;
  padding: 0 8px;
  border-radius: 6px;
  border: 1px solid var(--border-default, #e5e7eb);
  background: var(--surface-card, #ffffff);
  color: var(--text-secondary, #4b5563);
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
  user-select: none;
}

.model-selector-trigger:hover,
.model-selector-trigger.is-active {
  background: var(--bg-hover, #f3f4f6);
  border-color: var(--border-hover, #d1d5db);
  color: var(--text-primary, #111827);
}

/* 未配置态：虚线描边 + 弱化前景，与"已选中一个真实模型"明确区分 */
.model-selector-trigger.is-empty {
  border-style: dashed;
  border-color: var(--border-default);
  color: var(--text-muted);
  font-weight: 400;
}
.model-selector-trigger.is-empty .model-icon {
  opacity: 0.55;
}
.model-selector-trigger.is-empty:hover {
  border-color: var(--color-primary);
  color: var(--text-secondary);
}
.model-selector-empty {
  cursor: pointer;
  border-radius: var(--radius-md);
  transition: background-color 0.15s ease;
}
.model-selector-empty:hover {
  background: var(--bg-hover);
}

.dark .model-selector-trigger {
  background: #1c1c1f;
  border-color: #2e2e32;
  color: #9ca3af;
}

.dark .model-selector-trigger:hover,
.dark .model-selector-trigger.is-active {
  background: #27272b;
  border-color: #3f3f46;
  color: #f3f4f6;
}

.model-icon {
  display: inline-flex;
  align-items: center;
  color: var(--color-primary, #10b981);
}

.model-selector-name {
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-selector-ctx {
  font-size: 10px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: var(--text-muted, #9ca3af);
  background: var(--bg-secondary, #f3f4f6);
  padding: 1px 4px;
  border-radius: 4px;
  line-height: 1.2;
}

.dark .model-selector-ctx {
  background: #2a2a2e;
  color: #71717a;
}

.model-dropdown-arrow {
  color: var(--text-muted, #9ca3af);
}

/* 浮层菜单 */
.model-selector-dropdown {
  background: var(--bg-primary, #ffffff);
  border: 1px solid var(--border-default, #e5e7eb);
  border-radius: 10px;
  box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
  overflow: hidden;
  animation: dropdownIn 0.15s ease-out;
}

.dark .model-selector-dropdown {
  background: #18181b;
  border-color: #27272a;
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.5);
}

@keyframes dropdownIn {
  from {
    opacity: 0;
    transform: scale(0.96) translateY(-4px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

.model-selector-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px 6px;
  font-size: 11px;
  border-bottom: 1px solid var(--border-subtle, #f3f4f6);
}

.dark .model-selector-header {
  border-color: #27272a;
}

.model-selector-add {
  display: inline-flex;
  align-items: center;
  color: var(--color-primary, #10b981);
  cursor: pointer;
  background: transparent;
  border: none;
  font-size: 11px;
  transition: opacity 0.15s;
}

.model-selector-add:hover {
  opacity: 0.8;
}

.model-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 12px;
  cursor: pointer;
  transition: background 0.12s;
  font-size: 12px;
}

.model-option:hover {
  background: var(--bg-hover, #f9fafb);
}

.dark .model-option:hover {
  background: #27272a;
}

.model-option.is-selected {
  background: var(--color-primary-light, rgba(16, 185, 129, 0.08));
}

.model-option-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

.model-option-icon {
  color: var(--text-muted, #9ca3af);
  display: flex;
  align-items: center;
}

.model-option-name-wrap {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.model-option-name {
  font-weight: 500;
  color: var(--text-primary, #111827);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dark .model-option-name {
  color: #f3f4f6;
}

.model-option-raw-name {
  font-size: 10px;
  color: var(--text-muted, #9ca3af);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.model-option-ctx {
  font-size: 10px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: var(--text-muted, #9ca3af);
  background: var(--bg-secondary, #f3f4f6);
  padding: 1px 5px;
  border-radius: 4px;
}

.dark .model-option-ctx {
  background: #27272a;
}
</style>
