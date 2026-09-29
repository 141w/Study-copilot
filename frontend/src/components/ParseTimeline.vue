<template>
  <div class="mt-3 border border-[var(--border-default)] rounded-lg p-3" data-test="parse-timeline">
    <button
      type="button"
      class="flex items-center gap-2 w-full text-left cursor-pointer"
      @click="open = !open"
    >
      <el-icon class="w-4 h-4 text-[var(--text-muted)] transition-transform" :class="open ? 'rotate-90' : ''">
        <ArrowRight />
      </el-icon>
      <span class="text-xs font-medium text-[var(--text-secondary)]">解析时间线</span>
      <span v-if="stages.length" class="text-[10px] text-[var(--text-muted)]">
        {{ doneCount }}/{{ stageCount }} 阶段完成
      </span>
    </button>

    <div v-if="open" class="mt-3 space-y-1.5">
      <div v-if="loading" class="text-xs text-[var(--text-muted)]">加载中…</div>
      <div v-else-if="!stages.length" class="text-xs text-[var(--text-muted)]">
        旧文档暂无阶段记录
      </div>
      <div
        v-for="s in stages"
        :key="s.id"
        class="flex items-start gap-2 text-xs"
        :data-test="`span-${s.name}`"
        :data-status="s.status"
      >
        <span
          class="mt-1 w-2 h-2 rounded-full shrink-0"
          :class="statusDot(s.status)"
        />
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2">
            <span class="text-[var(--text-primary)] font-medium">{{ stageLabel(s.name) }}</span>
            <span class="text-[10px] px-1.5 rounded" :class="statusChip(s.status)">{{ statusLabel(s.status) }}</span>
            <span v-if="duration(s)" class="text-[10px] text-[var(--text-muted)] tabular-nums">{{ duration(s) }}</span>
          </div>
          <p v-if="s.detail" class="text-[10px] text-[var(--text-muted)] truncate">{{ s.detail }}</p>
          <p v-if="s.error" class="text-[10px] text-[var(--color-error)]" data-test="span-error">{{ s.error }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ArrowRight } from '@/components/icons'
import api from '../services/api'

interface SpanRow {
  id: string
  kind: string
  name: string
  status: string
  started_at: string | null
  ended_at: string | null
  detail: string | null
  error: string | null
  attempt: number
}

const props = defineProps<{ docId: string }>()

const open = ref(false)
const loading = ref(false)
const spans = ref<SpanRow[]>([])

/** 只呈现最近 attempt（历史 attempt 由 F13 提供折叠入口） */
const latestAttempt = computed(() => {
  if (!spans.value.length) return null
  return Math.max(...spans.value.map(s => s.attempt || 1))
})

/** 只统计 stage，不含 root（root 计入会显示成 6/6 误导） */
const stages = computed(() => {
  const maxA = latestAttempt.value
  return spans.value.filter(
    s => s.kind === 'stage' && (maxA === null || (s.attempt || 1) === maxA)
  )
})
const stageCount = computed(() => stages.value.length)
const doneCount = computed(() => stages.value.filter(s => s.status === 'done').length)

const LABELS: Record<string, string> = {
  parse: '文本解析',
  profile: '文档画像',
  chunk: '分块',
  embed: '向量化',
  index: '索引写入',
  finalize: '完成入库',
  process: '整体'
}

function stageLabel(n: string): string {
  return LABELS[n] || n
}

function statusLabel(s: string): string {
  return ({
    done: '完成',
    failed: '失败',
    cancelled: '未执行（上游失败）',
    skipped: '未执行（上游失败）',
    running: '进行中',
    pending: '未开始'
  } as Record<string, string>)[s] || s
}

function statusDot(s: string): string {
  // 四态：完成=实色对勾感 / 进行中=主题色脉冲（唯一常驻动画）/ 失败=红 / 取消跳过=灰虚线
  return {
    done: 'bg-emerald-500',
    failed: 'bg-red-500',
    cancelled: 'bg-transparent border border-dashed border-zinc-400',
    skipped: 'bg-transparent border border-dashed border-zinc-400',
    running: 'bg-[var(--color-primary,#f59e0b)] animate-pulse'
  }[s] || 'bg-zinc-300'
}

function statusChip(s: string): string {
  return {
    done: 'bg-emerald-500/10 text-emerald-600',
    failed: 'bg-red-500/10 text-red-600',
    cancelled: 'bg-zinc-500/10 text-zinc-500',
    skipped: 'bg-zinc-500/10 text-zinc-500',
    running: 'bg-[var(--color-primary,#f59e0b)]/10 text-[var(--color-primary,#d97706)]'
  }[s] || 'bg-zinc-500/10 text-zinc-500'
}

function duration(s: SpanRow): string {
  if (!s.started_at || !s.ended_at) return ''
  const a = Date.parse(s.started_at)
  const b = Date.parse(s.ended_at)
  if (!Number.isFinite(a) || !Number.isFinite(b) || b < a) return ''
  const ms = b - a
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`
}

let loadSeq = 0

async function load(): Promise<void> {
  if (!props.docId) return
  const id = props.docId
  const my = ++loadSeq
  loading.value = true
  try {
    const { data } = await api.get<{ spans: SpanRow[] }>(`/documents/${id}/parse-spans`)
    if (my !== loadSeq) return
    spans.value = Array.isArray(data?.spans) ? data.spans : []
  } catch {
    if (my === loadSeq) spans.value = []
  } finally {
    if (my === loadSeq) loading.value = false
  }
}

onMounted(load)
watch(() => props.docId, load)
</script>
