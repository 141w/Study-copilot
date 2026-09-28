<template>
  <div class="card p-6 mb-6" data-test="eval-lab">
    <div class="flex items-center justify-between mb-3">
      <div>
        <h3 class="text-sm font-semibold text-[var(--text-primary)]">检索评测台</h3>
        <p class="text-xs text-[var(--text-muted)] mt-1">
          选文档 + 贴问题 → 跑混合检索，看 hit@1 / hit@5 与命中切片。与调整后的检索参数联动。
        </p>
      </div>
      <el-button size="small" type="primary" :loading="running" data-test="eval-run" @click="run">
        运行评测
      </el-button>
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
          问题列表（每行一条，最多 30）
        </label>
        <el-input
          v-model="questionText"
          type="textarea"
          :rows="5"
          placeholder="什么是梯度下降？&#10;过拟合怎么缓解？"
          data-test="eval-questions"
        />
      </div>
    </div>

    <div v-if="report" class="mt-4">
      <div class="flex flex-wrap gap-3 text-xs mb-3">
        <span class="px-2 py-1 rounded bg-[var(--bg-secondary)]">
          题数 <b class="tabular-nums">{{ report.meta.n_questions }}</b>
        </span>
        <span class="px-2 py-1 rounded bg-emerald-500/10 text-emerald-600" data-test="eval-hit1">
          hit@1 <b class="tabular-nums">{{ pct(report.meta['hit_rate@1']) }}</b>
        </span>
        <span class="px-2 py-1 rounded bg-[var(--color-primary)]/10 text-[var(--color-primary)]" data-test="eval-hit5">
          hit@5 <b class="tabular-nums">{{ pct(report.meta['hit_rate@5']) }}</b>
        </span>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-xs">
          <thead>
            <tr class="text-left text-[var(--text-muted)] border-b border-[var(--border-default)]">
              <th class="py-1.5 pr-2">问题</th>
              <th class="py-1.5 pr-2">hit@1</th>
              <th class="py-1.5">Top 结果</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(r, i) in report.results"
              :key="i"
              class="border-b border-[var(--border-default)]"
            >
              <td class="py-1.5 pr-2 max-w-[180px] truncate">{{ r.question }}</td>
              <td class="py-1.5 pr-2">
                <span :class="r['hit@1'] ? 'text-emerald-600' : 'text-red-500'">
                  {{ r['hit@1'] ? '✓' : '✗' }}
                </span>
              </td>
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
import { onMounted, ref } from 'vue'
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
  'hit@1': boolean
  top: EvalHit[]
}
interface EvalReport {
  meta: Record<string, number | string | string[]> & {
    n_questions: number
    'hit_rate@1': number
    'hit_rate@5': number
  }
  results: EvalRow[]
}

const documentStore = useDocumentStore()
const documents = ref<{ id: string; filename: string }[]>([])
const selectedDocs = ref<string[]>([])
const questionText = ref('')
const running = ref(false)
const report = ref<EvalReport | null>(null)

function pct(v: number | string): string {
  const n = typeof v === 'number' ? v : Number(v)
  return `${Math.round((n || 0) * 100)}%`
}

async function run(): Promise<void> {
  const questions = questionText.value
    .split('\n')
    .map(s => s.trim())
    .filter(Boolean)
    .slice(0, 30)
  if (!selectedDocs.value.length) {
    ElMessage.warning('请先选择文档')
    return
  }
  if (!questions.length) {
    ElMessage.warning('请至少输入一个问题')
    return
  }
  running.value = true
  try {
    const { data } = await api.post<EvalReport>('/evaluation/run', {
      document_ids: selectedDocs.value,
      questions,
      top_k: 5
    })
    report.value = data
    ElMessage.success('评测完成')
  } catch {
    ElMessage.error('评测失败')
  } finally {
    running.value = false
  }
}

onMounted(async () => {
  await documentStore.fetchDocuments()
  documents.value = (documentStore.documents || [])
    .filter(d => d.status === 'ready')
    .map(d => ({ id: d.id, filename: d.filename }))
})
</script>
