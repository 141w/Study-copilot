<template>
  <div class="card p-6 mb-6" data-test="retrieval-settings">
    <div class="flex items-center justify-between mb-4">
      <div>
        <h3 class="text-sm font-semibold text-[var(--text-primary)]">检索参数调节</h3>
        <p class="text-xs text-[var(--text-muted)] mt-1">
          调整召回宽度与 RRF 融合。默认值与现网行为一致；改动即时生效（下次提问起）。
        </p>
      </div>
      <el-button size="small" :loading="saving" type="primary" @click="save">
        保存
      </el-button>
    </div>

    <div v-if="loading" class="text-xs text-[var(--text-muted)]">加载中…</div>
    <div v-else class="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-4">
      <div v-for="f in fields" :key="f.key">
        <div class="flex items-center justify-between mb-1">
          <label class="text-xs font-medium text-[var(--text-secondary)]">{{ f.label }}</label>
          <span class="text-xs text-[var(--color-primary)] tabular-nums" :data-test="`ret-val-${f.key}`">
            {{ display(f) }}
          </span>
        </div>
        <p class="text-[11px] text-[var(--text-muted)] mb-1.5 leading-snug">{{ f.hint }}</p>
        <p
          v-if="f.needsRerank && !rerankEnabled"
          class="text-[10px] text-[var(--text-muted)] mb-1"
          :data-test="`ret-rerank-off-${f.key}`"
        >
          当前重排已关闭，此项不生效
        </p>
        <el-slider
          v-model="form[f.key]"
          :min="f.min"
          :max="f.max"
          :step="f.step"
          :disabled="saving || (Boolean(f.needsRerank) && !rerankEnabled)"
          @change="dirty = true"
        />
      </div>
    </div>

    <div class="mt-4 flex items-center gap-2">
      <el-button size="small" @click="resetDefaults">恢复默认</el-button>
      <span v-if="dirty" class="text-[11px] text-[var(--color-warning)]">未保存的更改</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../services/api'

interface RetrievalForm {
  embedding_top_k: number
  vector_threshold: number
  keyword_threshold: number
  rerank_top_k: number
  rerank_threshold: number
  rrf_k: number
  rrf_vector_weight: number
  rrf_keyword_weight: number
}

const DEFAULTS: RetrievalForm = {
  embedding_top_k: 5,
  vector_threshold: 0,
  keyword_threshold: 0,
  rerank_top_k: 5,
  rerank_threshold: 0,
  rrf_k: 60,
  rrf_vector_weight: 1,
  rrf_keyword_weight: 1
}

const fields = [
  {
    key: 'embedding_top_k' as const,
    label: '召回条数 Top-K',
    hint: '向量+全文混合检索返回的切片上限。仅作用于常规问答路径（top_k≤10 的调用）；全篇总结等批量调用不受影响',
    min: 1,
    max: 50,
    step: 1
  },
  {
    key: 'rrf_k' as const,
    label: 'RRF 平滑常数 K',
    hint: '越大越平缓，对 Top1 偏置越小（默认 60）',
    min: 10,
    max: 150,
    step: 1
  },
  {
    key: 'rrf_vector_weight' as const,
    label: '向量路权重',
    hint: '与关键词路权重共同决定两路融合占比',
    min: 0,
    max: 1,
    step: 0.1
  },
  {
    key: 'rrf_keyword_weight' as const,
    label: '关键词路权重',
    hint: '与向量路权重共同决定两路融合占比',
    min: 0,
    max: 1,
    step: 0.1
  },
  {
    key: 'keyword_threshold' as const,
    label: '关键词阈值',
    hint: '词法通道 ts_rank 低于该值的片段不进融合（0 = 不过滤）',
    min: 0,
    max: 1,
    step: 0.05
  },
  {
    key: 'rerank_top_k' as const,
    label: '重排后条数',
    hint: 'CrossEncoder 重排后保留的结果数',
    min: 1,
    max: 30,
    step: 1,
    needsRerank: true
  },
  {
    key: 'rerank_threshold' as const,
    label: '重排分数阈值',
    hint: '重排分数低于该值被过滤（0 = 不过滤）',
    min: 0,
    max: 1,
    step: 0.05,
    needsRerank: true
  },
  {
    key: 'vector_threshold' as const,
    label: '向量相似度阈值',
    hint: '作用在融合后归一分（批次内最高分为 1.0）；第一名恒为 1.0，无法用它做拒答。0 = 不过滤',
    min: 0,
    max: 1,
    step: 0.05
  }
] as {
  key: keyof RetrievalForm
  label: string
  hint: string
  min: number
  max: number
  step: number
  needsRerank?: boolean
}[]

const form = reactive<RetrievalForm>({ ...DEFAULTS })
const loading = ref(true)
const saving = ref(false)
const dirty = ref(false)
/** F11：reranker 未启用时，rerank 两条滑杆置灰 */
const rerankEnabled = ref(true)

function display(f: (typeof fields)[number]): string {
  const v = form[f.key]
  return f.step < 1 ? Number(v).toFixed(f.step === 0.05 ? 2 : 1) : String(v)
}

function apply(obj: Partial<RetrievalForm>): void {
  for (const k of Object.keys(DEFAULTS) as (keyof RetrievalForm)[]) {
    if (obj[k] !== undefined && obj[k] !== null) {
      form[k] = Number(obj[k])
    }
  }
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const { data } = await api.get<Partial<RetrievalForm>>('/config/retrieval')
    apply(data || {})
    // F11：读取 reranker 开关（关闭时 rerank 滑杆置灰）
    try {
      const st = await api.get<{ reranker_enabled?: boolean }>('/config/status')
      rerankEnabled.value = st.data?.reranker_enabled !== false
    } catch {
      rerankEnabled.value = true
    }
    dirty.value = false
  } catch {
    ElMessage.error('检索参数加载失败')
  } finally {
    loading.value = false
  }
}

async function save(): Promise<void> {
  saving.value = true
  try {
    const { data } = await api.put<Partial<RetrievalForm>>('/config/retrieval', { ...form })
    apply(data || {})
    dirty.value = false
    ElMessage.success('检索参数已保存')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

function resetDefaults(): void {
  apply(DEFAULTS)
  dirty.value = true
}

onMounted(load)
</script>
