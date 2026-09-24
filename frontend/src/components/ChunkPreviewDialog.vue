<template>
  <el-dialog
    v-model="visible"
    title="分块预览"
    width="min(880px, 96vw)"
    destroy-on-close
    @closed="reset"
  >
    <div class="space-y-4">
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div>
          <label class="block text-xs font-medium text-[var(--text-secondary)] mb-1">策略</label>
          <el-select v-model="strategy" class="w-full">
            <el-option label="自动" value="auto" />
            <el-option label="固定" value="fixed" />
            <el-option label="语义（预览跳过向量）" value="semantic" />
            <el-option label="层级" value="hierarchical" />
          </el-select>
        </div>
        <div>
          <label class="block text-xs font-medium text-[var(--text-secondary)] mb-1">目标块大小</label>
          <el-input v-model.number="chunkSize" type="number" min="80" max="4000" placeholder="默认" />
        </div>
        <div class="flex items-end">
          <el-button type="primary" :loading="loading" class="w-full" @click="runPreview">
            运行预览
          </el-button>
        </div>
      </div>

      <div>
        <label class="block text-xs font-medium text-[var(--text-secondary)] mb-1">粘贴文本（≤64k 字符）</label>
        <el-input
          v-model="text"
          type="textarea"
          :rows="6"
          :maxlength="64000"
          placeholder="粘贴要预览分块的纯文本 / Markdown…"
        />
        <div class="text-[11px] text-[var(--text-muted)] mt-1 tabular-nums">{{ text.length }} / 64000</div>
      </div>

      <div v-if="result" class="space-y-3" data-test="preview-result">
        <!-- 策略链与拒绝原因 -->
        <div class="rounded-xl border border-[var(--border-default)] p-3 bg-[var(--bg-secondary)]/40">
          <div class="text-xs font-semibold text-[var(--text-primary)] mb-1.5">
            采用：<span class="text-[var(--color-primary)]">{{ result.selected_strategy }}</span>
            <span v-if="result.fallback_used" class="ml-2 text-[var(--color-warning)]">（兜底 fixed）</span>
          </div>
          <div class="text-[11px] text-[var(--text-muted)] mb-1">候选链：{{ result.chain.join(' → ') }}</div>
          <div v-if="result.rejected?.length" class="space-y-0.5 text-[11px]">
            <div v-for="(r, i) in result.rejected" :key="i" class="text-[var(--color-error)]">
              被拒：{{ r.strategy }}（{{ r.reason }}）
            </div>
          </div>
          <div v-else class="text-[11px] text-[var(--text-muted)]">无被拒层级</div>
        </div>

        <!-- 画像指标 -->
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
          <div v-for="(val, key) in profileCards" :key="key" class="card !p-3 !rounded-lg">
            <div class="text-[10px] text-[var(--text-muted)]">{{ key }}</div>
            <div class="text-sm font-semibold text-[var(--text-primary)] tabular-nums">{{ val }}</div>
          </div>
        </div>

        <!-- 统计 + 块列表 -->
        <div class="text-xs text-[var(--text-secondary)]">
          块数 {{ result.stats?.count }}
          · 均值 {{ result.stats?.avg_chars }}
          · 最小 {{ result.stats?.min }}
          · 最大 {{ result.stats?.max }}
          <span v-if="result.stats?.truncated_to" class="text-[var(--color-warning)]">
            · 已截断至 {{ result.stats.truncated_to }}
          </span>
        </div>
        <div class="max-h-72 overflow-y-auto space-y-2">
          <div
            v-for="c in result.chunks"
            :key="c.seq"
            class="card !p-3 !rounded-lg"
            data-test="preview-chunk"
          >
            <div class="flex items-center justify-between text-[11px] text-[var(--text-muted)] mb-1">
              <span>#{{ c.seq }} · P{{ c.page || '-' }}</span>
              <span v-if="c.context_header" class="truncate max-w-[60%]">{{ c.context_header }}</span>
            </div>
            <p class="text-xs text-[var(--text-secondary)] leading-relaxed line-clamp-4">{{ c.content }}</p>
          </div>
        </div>
      </div>

      <p v-if="error" class="text-sm text-[var(--color-error)]" data-test="preview-error">{{ error }}</p>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import api from '@/services/api'

const props = defineProps<{ visible: boolean; initialText?: string }>()
const emit = defineEmits<{ (e: 'update:visible', v: boolean): void }>()

const visible = computed({
  get: () => props.visible,
  set: (v: boolean) => emit('update:visible', v),
})

const strategy = ref('auto')
const chunkSize = ref<number | undefined>(undefined)
const text = ref(props.initialText || '')
const loading = ref(false)
const error = ref('')
const result = ref<any>(null)

const profileCards = computed(() => {
  const p = result.value?.profile || {}
  return {
    字符: p.total_chars ?? '—',
    行数: p.total_lines ?? '—',
    标题: p.md_heading_total ?? '—',
    主层级: p.dominant_heading_level ?? '—',
  }
})

function reset(): void {
  result.value = null
  error.value = ''
  loading.value = false
  if (props.initialText !== undefined) text.value = props.initialText
}

async function runPreview(): Promise<void> {
  error.value = ''
  result.value = null
  if (!text.value.trim()) {
    error.value = '请先粘贴文本'
    return
  }
  loading.value = true
  try {
    const res = await api.post('/documents/preview-chunking', {
      text: text.value,
      strategy: strategy.value,
      chunk_size: chunkSize.value || undefined,
    })
    result.value = res.data
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '预览失败'
  } finally {
    loading.value = false
  }
}

// 打开时若有初始文本，自动预览
import { watch } from 'vue'
watch(
  () => props.visible,
  (v) => {
    if (v) {
      text.value = props.initialText || ''
      if (text.value.trim()) runPreview()
    }
  },
  { immediate: true }
)
</script>
