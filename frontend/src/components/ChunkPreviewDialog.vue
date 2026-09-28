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
          <div class="flex items-center flex-wrap gap-2 text-xs font-semibold text-[var(--text-primary)] mb-1.5">
            <span>采用：</span>
            <span class="px-2 py-0.5 rounded font-mono font-bold text-xs bg-[var(--color-primary-light,rgba(0,0,0,0.06))] text-[var(--color-primary)]">
              {{ result.selected_strategy }}
            </span>
            <span v-if="result.fallback_used" class="px-2 py-0.5 rounded text-[11px] bg-amber-50 text-amber-600 dark:bg-amber-950/40 dark:text-amber-400">
              （兜底 fixed）
            </span>
          </div>
          <div class="text-[11px] text-[var(--text-muted)] mb-1.5">候选链：{{ result.chain?.join(' → ') }}</div>
          <div v-if="result.rejected?.length" class="flex flex-wrap gap-1.5 text-[11px]">
            <div
              v-for="(r, i) in result.rejected"
              :key="i"
              class="px-2 py-0.5 rounded bg-rose-50 text-rose-600 dark:bg-rose-950/30 dark:text-rose-400 border border-rose-100 dark:border-rose-900/50"
            >
              被拒：{{ r.strategy }}（{{ r.reason }}）
            </div>
          </div>
          <div v-else class="text-[11px] text-[var(--text-muted)]">无被拒层级</div>
        </div>

        <!-- 画像指标 (复刻 WeKnora profile-grid 6 宫格) -->
        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2">
          <div v-for="(card, idx) in profileCards" :key="idx" class="rounded-xl border border-[var(--border-default)] p-2.5 bg-[var(--surface-card)]">
            <div class="text-[10px] text-[var(--text-muted)] mb-0.5">{{ card.label }}</div>
            <div class="text-sm font-semibold text-[var(--text-primary)] tabular-nums">{{ card.val }}</div>
            <div v-if="card.sub" class="text-[9px] text-[var(--text-muted)] mt-0.5">{{ card.sub }}</div>
          </div>
        </div>

        <!-- 统计 + 块列表 -->
        <div class="flex items-center justify-between text-xs text-[var(--text-secondary)] px-1">
          <div>
            块数 {{ result.stats?.count }}
            · 均值 {{ result.stats?.avg_chars }}
            · 最小 {{ result.stats?.min }}
            · 最大 {{ result.stats?.max }}
            <span v-if="result.stats?.truncated_to" class="text-[var(--color-warning)]">
              · 已截断至 {{ result.stats.truncated_to }}
            </span>
          </div>
        </div>

        <div class="max-h-80 overflow-y-auto space-y-2 pr-1">
          <div
            v-for="c in result.chunks"
            :key="c.seq"
            class="rounded-xl border border-[var(--border-default)] p-3 bg-[var(--surface-card)] hover:border-[var(--border-hover)] transition-colors"
            data-test="preview-chunk"
          >
            <div class="flex items-center justify-between gap-2 text-[11px] text-[var(--text-muted)] mb-1.5">
              <div class="flex items-center gap-1.5 min-w-0">
                <span class="font-mono font-bold px-1.5 py-0.5 rounded bg-[var(--bg-secondary)] text-[var(--text-primary)]">
                  #{{ c.seq }}
                </span>
                <span>{{ c.content?.length || 0 }} 字符</span>
                <span v-if="c.char_start != null && c.char_end != null">
                  [{{ c.char_start }}:{{ c.char_end }}]
                </span>
                <span v-if="c.page">· P{{ c.page }}</span>
              </div>
              <span v-if="c.context_header" class="truncate max-w-[50%] px-1.5 py-0.5 rounded bg-[var(--bg-secondary)] text-[10px]" :title="c.context_header">
                {{ c.context_header }}
              </span>
            </div>
            <p class="text-xs text-[var(--text-secondary)] font-mono leading-relaxed whitespace-pre-wrap line-clamp-6 select-text">{{ c.content }}</p>
          </div>
        </div>
      </div>

      <p v-if="error" class="text-sm text-[var(--color-error)]" data-test="preview-error">{{ error }}</p>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
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
  const chapterCount = (p.chinese_chapter_count || 0) + (p.english_chapter_count || 0) + (p.numbered_section_count || 0)
  return [
    { label: '总行数', val: p.total_lines ?? '—' },
    { label: '总字符', val: p.total_chars ?? '—' },
    { label: 'Markdown 标题', val: p.md_heading_total ?? '—', sub: p.dominant_heading_level ? `主 H${p.dominant_heading_level}` : '' },
    { label: '分页符', val: p.form_feed_count ?? 0 },
    { label: '章节标记', val: chapterCount },
    { label: '平均行长', val: p.avg_line_len ? `${p.avg_line_len} 字` : '—' },
  ]
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
