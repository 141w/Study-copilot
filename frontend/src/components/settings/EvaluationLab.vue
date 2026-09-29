<template>
  <div class="card p-6 mb-6" data-test="eval-lab">
    <div class="flex items-center justify-between mb-3">
      <div>
        <h3 class="text-sm font-semibold text-[var(--text-primary)]">检索评测台</h3>
        <p class="text-xs text-[var(--text-muted)] mt-1">
          选文档 + 贴问题（每行一题，可选第二列期望文档 id，Tab/逗号分隔）→ 走生产检索，
          按期望集计算 hit@k / Recall@k / MRR。
        </p>
      </div>
      <div class="flex items-center gap-2">
        <el-button
          v-if="report"
          size="small"
          data-test="eval-export"
          @click="exportJson"
        >
          导出 JSON
        </el-button>
        <el-button size="small" type="primary" :loading="running" data-test="eval-run" @click="run">
          运行评测
        </el-button>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div>
        <label class="text-xs font-medium text-[var(--text-secondary)] mb-1.5 block">文档（多选）</label>
        <el-select
          v-model="selectedDocs"
          multiple
          filterable
          collapse-tags
          placeholder="选择要评测的文档"
          class="w-full"
          data-test="eval-docs"
        >
          <el-option v-for="d in documents" :key="d.id" :label="d.filename" :value="d.id" />
        </el-select>
      </div>
      <div>
        <label class="text-xs font-medium text-[var(--text-secondary)] mb-1.5 block">
          问题列表（每行一题，可选「问题&lt;Tab&gt;期望文档id」；最多 200）
        </label>
        <el-input
          v-model="questionText"
          type="textarea"
          :rows="5"
          placeholder="什么是梯度下降？&#9;d1&#10;过拟合怎么缓解？&#9;d2"
          data-test="eval-questions"
        />
      </div>
    </div>

    <p v-if="!hasAnyExpected" class="mt-2 text-xs text-amber-600" data-test="eval-no-expected">
      未录入期望答案，指标不可用于比较。请在问题后用 Tab 补上期望文档 id。
    </p>

    <div v-if="report" class="mt-4">
      <!-- 本次生效参数摘要带 -->
      <div
        class="mb-3 px-3 py-2 rounded bg-[var(--bg-secondary)] text-[10px] text-[var(--text-muted)] flex flex-wrap gap-x-3 gap-y-1"
        data-test="eval-params-band"
      >
        <span>本次生效参数</span>
        <span>embedding：<b>{{ report.meta.embedding_model || '—' }}</b></span>
        <span>top_k：<b>{{ report.meta.top_k }}</b></span>
        <span>rrf_k：<b>{{ report.meta.rrf_k ?? '—' }}</b></span>
        <span>权重 v/k：<b>{{ report.meta.rrf_vector_weight ?? '—' }}/{{ report.meta.rrf_keyword_weight ?? '—' }}</b></span>
        <span>FTS：<b>{{ report.meta.fts_config || '—' }}</b></span>
      </div>

      <div v-if="showPercentages" class="flex flex-wrap gap-3 text-xs mb-3">
        <span class="px-2 py-1 rounded bg-[var(--bg-secondary)]">
          题数 <b class="tabular-nums">{{ report.meta.n_questions }}</b>
        </span>
        <span class="px-2 py-1 rounded bg-emerald-500/10 text-emerald-600" data-test="eval-hit1">
          hit@1 <b class="tabular-nums">{{ pct(report.meta['hit_rate@1']) }}</b>
        </span>
        <span class="px-2 py-1 rounded bg-[var(--color-primary)]/10 text-[var(--color-primary)]" data-test="eval-hit5">
          hit@{{ report.meta.top_k }} <b class="tabular-nums">{{ pct(report.meta[`hit_rate@${report.meta.top_k}`] ?? report.meta['hit_rate@5']) }}</b>
        </span>
        <span class="px-2 py-1 rounded bg-[var(--bg-secondary)]">
          Recall@k <b class="tabular-nums">{{ pct(report.meta[`recall@${report.meta.top_k}`] ?? report.meta['recall@5'] ?? 0) }}</b>
        </span>
        <span class="px-2 py-1 rounded bg-[var(--bg-secondary)]">
          MRR <b class="tabular-nums">{{ pct(report.meta[`mrr@${report.meta.top_k}`] ?? report.meta['mrr@5'] ?? 0) }}</b>
        </span>
      </div>
      <p v-else class="mb-3 text-xs text-amber-600" data-test="eval-no-expected-banner">
        未录入期望答案，指标不可用于比较
      </p>

      <div class="overflow-x-auto">
        <table class="w-full text-xs">
          <thead>
            <tr class="text-left text-[var(--text-muted)] border-b border-[var(--border-default)]">
              <th class="py-1.5 pr-2">问题</th>
              <th class="py-1.5 pr-2">期望文档</th>
              <th class="py-1.5 pr-2">命中@1</th>
              <th class="py-1.5 pr-2">命中@k</th>
              <th class="py-1.5 pr-2">Recall@k</th>
              <th class="py-1.5 pr-2">MRR</th>
              <th class="py-1.5">Top 结果</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(r, i) in report.results"
              :key="i"
              class="border-b border-[var(--border-default)]"
            >
              <td class="py-1.5 pr-2 max-w-[160px] truncate">{{ r.question }}</td>
              <td class="py-1.5 pr-2 max-w-[120px] truncate">
                <span v-if="r.expected?.length">{{ r.expected.join(', ') }}</span>
                <span v-else class="text-amber-600" data-test="row-no-expected">未录入</span>
              </td>
              <td class="py-1.5 pr-2">
                <span :class="r['hit@1'] ? 'text-emerald-600' : 'text-zinc-400'">
                  {{ r['hit@1'] ? '✓' : '—' }}
                </span>
              </td>
              <td class="py-1.5 pr-2">
                <span :class="hitK(r) ? 'text-emerald-600' : 'text-zinc-400'">
                  {{ hitK(r) ? '✓' : '—' }}
                </span>
              </td>
              <td class="py-1.5 pr-2 tabular-nums">{{ num(r['recall@top_k'] ?? r[`recall@${report.meta.top_k}`]) }}</td>
              <td class="py-1.5 pr-2 tabular-nums">{{ num(r['mrr@top_k'] ?? r[`mrr@${report.meta.top_k}`]) }}</td>
              <td class="py-1.5">
                <div v-if="r.top?.length" class="space-y-0.5">
                  <div v-for="(t, j) in r.top.slice(0, 2)" :key="j" class="text-[10px] text-[var(--text-muted)] truncate">
                    {{ t.preview || t.document_id.slice(0, 8) }}
                    <span class="tabular-nums text-[var(--color-primary)]">{{ t.score }}</span>
                  </div>
                </div>
                <span v-else class="text-[var(--text-muted)]">无</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../services/api'
import { useDocumentStore } from '../../stores/document'

interface EvalHit {
  document_id: string
  chunk_id: string
  score: number
  preview: string
}
interface EvalRow {
  question: string
  expected?: string[]
  'hit@1': boolean
  'hit@5'?: boolean
  'hit@k'?: boolean
  'recall@top_k'?: number
  'mrr@top_k'?: number
  [key: string]: unknown
  top: EvalHit[]
  warning?: string
}
interface EvalReport {
  meta: Record<string, number | string | string[] | Record<string, unknown>> & {
    n_questions: number
    'hit_rate@1': number
    'hit_rate@5'?: number
    top_k: number
  }
  results: EvalRow[]
}

const documentStore = useDocumentStore()
const documents = ref<{ id: string; filename: string }[]>([])
const selectedDocs = ref<string[]>([])
const questionText = ref('')
const running = ref(false)
const report = ref<EvalReport | null>(null)

const hasAnyExpected = computed(() =>
  parseQuestions().some(p => p.expected.length > 0)
)
const showPercentages = computed(() => {
  if (!report.value) return false
  return report.value.results.some(r => (r.expected || []).length > 0)
})

function pct(v: unknown): string {
  const n = typeof v === 'number' ? v : Number(v ?? 0)
  return `${Math.round((Number.isFinite(n) ? n : 0) * 100)}%`
}
function num(v: unknown): string {
  const n = typeof v === 'number' ? v : Number(v ?? 0)
  return Number.isFinite(n) ? n.toFixed(2) : '0.00'
}
function hitK(r: EvalRow): boolean {
  const k = report.value?.meta.top_k
  return Boolean(r[`hit@${k}`] ?? r['hit@5'] ?? r['hit@k'])
}

/** 每行：问题[Tab/逗号]期望文档id（可多个，逗号分隔） */
function parseQuestions(): { question: string; expected: string[] }[] {
  return questionText.value
    .split('\n')
    .map(s => s.trim())
    .filter(Boolean)
    .slice(0, 200)
    .map(line => {
      const parts = line.split(/[\t,，]/).map(s => s.trim()).filter(Boolean)
      return { question: parts[0] || '', expected: parts.slice(1) }
    })
    .filter(p => p.question)
}

async function run(): Promise<void> {
  const parsed = parseQuestions()
  if (!selectedDocs.value.length) {
    ElMessage.warning('请先选择文档')
    return
  }
  if (!parsed.length) {
    ElMessage.warning('请至少输入一个问题')
    return
  }
  running.value = true
  try {
    const { data } = await api.post<EvalReport>('/evaluation/run', {
      document_ids: selectedDocs.value,
      questions: parsed.map(p => p.question),
      expected: parsed.map(p => p.expected),
      top_k: 5
    })
    report.value = data
    if (!parsed.some(p => p.expected.length)) {
      ElMessage.warning('未录入期望答案，指标不可用于比较')
    } else {
      ElMessage.success('评测完成')
    }
  } catch {
    ElMessage.error('评测失败')
  } finally {
    running.value = false
  }
}

function exportJson(): void {
  if (!report.value) return
  const blob = new Blob([JSON.stringify(report.value, null, 2)], {
    type: 'application/json'
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `retrieval-eval-${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('已导出 JSON')
}

onMounted(async () => {
  await documentStore.fetchDocuments()
  documents.value = (documentStore.documents || [])
    .filter(d => d.status === 'ready')
    .map(d => ({ id: d.id, filename: d.filename }))
})
</script>
