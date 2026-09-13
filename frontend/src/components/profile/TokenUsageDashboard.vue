<template>
  <div class="space-y-6">
    <!-- ── 顶部控制栏与操作 ── -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-default)]">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-xl bg-[var(--color-primary-light)] text-[var(--color-primary)] flex items-center justify-center">
          <el-icon :size="20"><Lightning /></el-icon>
        </div>
        <div>
          <div>
            <h3 class="text-sm font-semibold text-[var(--text-primary)]">Token 消耗与多模态用量看板</h3>
          </div>
        </div>
      </div>

      <div class="flex items-center gap-2.5 flex-wrap self-end sm:self-center">
        <!-- 统计时间跨度 -->
        <el-radio-group v-model="selectedDays" size="small" @change="handleDaysChange">
          <el-radio-button :value="7" :label="7">7天</el-radio-button>
          <el-radio-button :value="30" :label="30">30天</el-radio-button>
          <el-radio-button :value="90" :label="90">90天</el-radio-button>
          <el-radio-button :value="0" :label="0">全部</el-radio-button>
        </el-radio-group>

        <!-- 同步课堂数据按钮 -->
        <el-button
          size="small"
          :loading="usageStore.syncing"
          @click="handleSyncClassroom"
          title="从 OpenMAIC 课堂引擎同步课件生成用量"
        >
          <el-icon class="mr-1"><RefreshRight /></el-icon>同步课堂
        </el-button>

        <!-- 刷新 -->
        <el-button
          size="small"
          :loading="usageStore.loading"
          @click="loadData"
        >
          <el-icon class="mr-1"><Refresh /></el-icon>刷新
        </el-button>
      </div>
    </div>

    <!-- ── 4 个核心指标卡片 ── -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
      <!-- 累计 Token 消耗 -->
      <div class="p-4 rounded-xl bg-[var(--surface-card)] border border-[var(--border-default)] flex flex-col justify-between">
        <div class="flex items-center justify-between text-[var(--text-muted)]">
          <div class="flex items-center gap-1.5">
            <el-icon class="text-indigo-400"><Cpu /></el-icon>
            <span class="text-xs font-medium">累计 Token 消耗</span>
          </div>
        </div>
        <div class="mt-3">
          <div class="text-2xl font-bold font-mono text-[var(--text-primary)] tabular-nums">
            {{ formatNum(usageStore.totals.total_tokens) }}
          </div>
          <div class="flex items-center gap-2 text-[11px] text-[var(--text-muted)] mt-1 truncate font-mono">
            <span>输入: {{ formatNum(usageStore.totals.prompt_tokens) }}</span>
            <span>•</span>
            <span>输出: {{ formatNum(usageStore.totals.completion_tokens) }}</span>
          </div>
        </div>
      </div>

      <!-- 课堂生成消耗 -->
      <div class="p-4 rounded-xl bg-[var(--surface-card)] border border-[var(--border-default)] flex flex-col justify-between">
        <div class="flex items-center justify-between text-[var(--text-muted)]">
          <div class="flex items-center gap-1.5">
            <el-icon class="text-violet-400"><VideoPlay /></el-icon>
            <span class="text-xs font-medium">互动课堂生成</span>
          </div>
        </div>
        <div class="mt-3">
          <div class="text-2xl font-bold font-mono text-violet-500 dark:text-violet-400 tabular-nums">
            {{ formatNum(usageStore.totals.classroom_tokens) }}
          </div>
        </div>
      </div>

      <!-- AI 问答与研讨 -->
      <div class="p-4 rounded-xl bg-[var(--surface-card)] border border-[var(--border-default)] flex flex-col justify-between">
        <div class="flex items-center justify-between text-[var(--text-muted)]">
          <div class="flex items-center gap-1.5">
            <el-icon class="text-emerald-400"><ChatDotSquare /></el-icon>
            <span class="text-xs font-medium">AI 问答与研讨</span>
          </div>
        </div>
        <div class="mt-3">
          <div class="text-2xl font-bold font-mono text-emerald-500 dark:text-emerald-400 tabular-nums">
            {{ formatNum(usageStore.totals.chat_tokens) }}
          </div>
        </div>
      </div>

      <!-- 调用总请求数 -->
      <div class="p-4 rounded-xl bg-[var(--surface-card)] border border-[var(--border-default)] flex flex-col justify-between">
        <div class="flex items-center justify-between text-[var(--text-muted)]">
          <div class="flex items-center gap-1.5">
            <el-icon class="text-sky-400"><Tickets /></el-icon>
            <span class="text-xs font-medium">模型调用频次</span>
          </div>
        </div>
        <div class="mt-3">
          <div class="text-2xl font-bold font-mono text-[var(--text-primary)] tabular-nums">
            {{ usageStore.totals.requests.toLocaleString() }} <span class="text-xs font-normal text-[var(--text-muted)] font-sans">次</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ── 多模态资源汇总 Chips ── -->
    <div v-if="usageStore.byKind.length > 0" class="flex flex-wrap items-center gap-2">
      <span class="text-xs text-[var(--text-muted)] mr-1">模态分布:</span>
      <div
        v-for="k in usageStore.byKind"
        :key="k.kind"
        class="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-[var(--border-default)] bg-[var(--surface-card)] text-xs"
      >
        <el-icon :class="getKindIconColor(k.kind)">
          <component :is="getKindIcon(k.kind)" />
        </el-icon>
        <span class="font-medium text-[var(--text-primary)]">{{ k.label }}</span>
        <span class="font-mono text-indigo-400 font-semibold">
          {{ k.kind === 'llm' ? formatNum(k.tokens) + ' Tokens' : k.quantity.toLocaleString() + ' ' + (k.unit === 'image' ? '张' : k.unit === 'character' ? '字符' : k.unit) }}
        </span>
        <span class="text-[10px] text-[var(--text-muted)]">({{ k.requests }}次)</span>
      </div>
    </div>

    <!-- ── 每日消耗趋势图 (ECharts Area / Bar Chart) ── -->
    <div class="p-4 md:p-5 rounded-xl bg-[var(--surface-card)] border border-[var(--border-default)]">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div>
          <div>
            <h4 class="text-sm font-semibold text-[var(--text-primary)]">每日消耗趋势</h4>
          </div>
        </div>

        <div class="flex items-center gap-2 flex-wrap">
          <!-- 统计指标切换 (Tokens vs 调用次数) -->
          <el-radio-group v-model="metricType" size="small" @change="renderChart">
            <el-radio-button :value="'tokens'" :label="'tokens'">Tokens</el-radio-button>
            <el-radio-button :value="'requests'" :label="'requests'">调用次数</el-radio-button>
          </el-radio-group>

          <!-- 图表形态切换 (折线图 vs 柱状图) -->
          <el-radio-group v-model="chartType" size="small" @change="renderChart">
            <el-radio-button :value="'line'" :label="'line'">折线图</el-radio-button>
            <el-radio-button :value="'bar'" :label="'bar'">柱状图</el-radio-button>
          </el-radio-group>

          <!-- 业务来源快速筛选 -->
          <el-select
            v-model="selectedSource"
            size="small"
            class="w-28"
            @change="handleSourceChange"
          >
            <el-option label="全部来源" value="all" />
            <el-option label="互动课堂" value="classroom" />
            <el-option label="AI 问答" value="chat" />
            <el-option label="深度研究" value="agent" />
          </el-select>
        </div>
      </div>

      <div v-if="usageStore.dailyTrend.length > 0" ref="chartRef" class="w-full h-64" />
      <div
        v-else
        class="h-44 flex flex-col items-center justify-center text-[var(--text-muted)] text-sm"
      >
        <el-icon class="text-2xl mb-1.5"><DataLine /></el-icon>
        <span>暂无所选周期内的消耗数据</span>
      </div>
    </div>

    <!-- ── 两个并列下栏：各模型详细消耗 + 最近调用流水 ── -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <!-- 1. 模型用量分布明细 -->
      <div class="p-4 md:p-5 rounded-xl bg-[var(--surface-card)] border border-[var(--border-default)] flex flex-col">
        <div class="flex items-center justify-between pb-3 border-b border-[var(--border-default)] mb-3">
          <div class="flex items-center gap-2">
            <el-icon class="text-indigo-400"><Cpu /></el-icon>
            <h4 class="text-sm font-semibold text-[var(--text-primary)]">模型用量分布</h4>
          </div>
          <span class="text-xs text-[var(--text-muted)]">按累计消耗降序</span>
        </div>

        <div v-if="usageStore.byModel.length > 0" class="overflow-x-auto">
          <table class="w-full text-xs">
            <thead>
              <tr class="text-[var(--text-muted)] border-b border-[var(--border-default)] text-left">
                <th class="py-2 pr-2 font-medium">模型 / 服务商</th>
                <th class="py-2 px-2 font-medium text-right">调用次数</th>
                <th class="py-2 px-2 font-medium text-right">总消耗</th>
                <th class="py-2 pl-2 font-medium text-right w-24">占比</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-[var(--border-default)]">
              <tr
                v-for="m in usageStore.byModel"
                :key="m.model_name"
                class="hover:bg-[var(--bg-secondary)] transition-colors"
              >
                <td class="py-2.5 pr-2">
                  <div class="font-mono font-medium text-[var(--text-primary)] truncate max-w-[160px]" :title="m.model_name">
                    {{ m.model_name }}
                  </div>
                  <span class="text-[10px] text-[var(--text-muted)]">
                      {{ m.kind === 'llm' ? '大模型' : m.kind }}
                    </span>
                </td>
                <td class="py-2.5 px-2 text-right tabular-nums text-[var(--text-secondary)]">
                  {{ m.requests }} 次
                </td>
                <td class="py-2.5 px-2 text-right tabular-nums font-mono font-medium text-[var(--text-primary)]">
                  {{ m.kind === 'llm' ? formatNum(m.total_tokens) : m.quantity.toLocaleString() + ' ' + m.unit }}
                </td>
                <td class="py-2.5 pl-2 text-right tabular-nums">
                  <div class="flex items-center justify-end gap-1.5">
                    <span class="text-[11px] text-[var(--text-muted)]">
                      {{ calcPercent(m.total_tokens, usageStore.totals.total_tokens) }}%
                    </span>
                    <div class="w-12 h-1.5 rounded-full bg-neutral-500/20 overflow-hidden">
                      <div
                        class="h-full bg-indigo-500 rounded-full"
                        :style="{ width: calcPercent(m.total_tokens, usageStore.totals.total_tokens) + '%' }"
                      />
                    </div>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="py-8 text-center text-xs text-[var(--text-muted)]">
          暂无模型消耗数据
        </div>
      </div>

      <!-- 2. 最近用量记录明细 -->
      <div class="p-4 md:p-5 rounded-xl bg-[var(--surface-card)] border border-[var(--border-default)] flex flex-col">
        <div class="flex items-center justify-between pb-3 border-b border-[var(--border-default)] mb-3">
          <div class="flex items-center gap-2">
            <el-icon class="text-emerald-400"><Clock /></el-icon>
            <h4 class="text-sm font-semibold text-[var(--text-primary)]">最近流水明细</h4>
          </div>
          <span class="text-xs text-[var(--text-muted)]">最新 30 条</span>
        </div>

        <div v-if="usageStore.recentRecords.length > 0" class="overflow-y-auto max-h-80 space-y-2 pr-1">
          <div
            v-for="rec in usageStore.recentRecords"
            :key="rec.id"
            class="p-2.5 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-default)] flex items-center justify-between text-xs"
          >
            <div class="min-w-0 pr-2">
              <div class="flex items-center gap-2 flex-wrap">
                <span
                  class="px-1.5 py-0.5 rounded text-[10px] font-medium"
                  :class="getSourceBadgeClass(rec.source)"
                >
                  {{ rec.source_label }}
                </span>
                <span class="font-mono text-[var(--text-primary)] truncate max-w-[140px]" :title="rec.model_name">
                  {{ rec.model_name }}
                </span>
              </div>
              <div class="text-[11px] text-[var(--text-muted)] mt-1">
                {{ formatTime(rec.created_at) }}
              </div>
            </div>

            <div class="text-right shrink-0">
              <div class="font-semibold text-[var(--text-primary)] font-mono">
                {{ rec.kind === 'llm' ? formatNum(rec.total_tokens) + ' T' : rec.quantity + ' ' + rec.unit }}
              </div>
              <div v-if="rec.kind === 'llm'" class="flex items-center justify-end gap-1.5 text-[10px] text-[var(--text-muted)] mt-0.5">
                <span class="inline-flex items-center gap-0.5">
                  <span class="text-[9px] px-1 py-0.2 rounded bg-neutral-500/10 text-neutral-400 font-sans">入</span>
                  <span class="font-mono">{{ formatNum(rec.prompt_tokens) }}</span>
                </span>
                <span>•</span>
                <span class="inline-flex items-center gap-0.5">
                  <span class="text-[9px] px-1 py-0.2 rounded bg-neutral-500/10 text-neutral-400 font-sans">出</span>
                  <span class="font-mono">{{ formatNum(rec.completion_tokens) }}</span>
                </span>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="py-8 text-center text-xs text-[var(--text-muted)]">
          暂无最近流水记录
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Refresh,
  RefreshRight,
  DataLine,
  Cpu,
  Picture,
  Headset,
  Clock,
} from '@element-plus/icons-vue'
import {
  Lightning,
  Tickets,
  ChatDotSquare,
  VideoPlay,
  Microphone,
} from '@/components/icons'
import * as echarts from 'echarts/core'
import { LineChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'

import { useUsageStore, type UsageDaily } from '@/stores/usage'
import { useThemeStore } from '@/stores/theme'

echarts.use([LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, SVGRenderer])

const usageStore = useUsageStore()
const themeStore = useThemeStore()

const selectedDays = ref(7)
const selectedSource = ref('all')
const chartType = ref<'line' | 'bar'>('line')
const metricType = ref<'tokens' | 'requests'>('tokens')

const chartRef = ref<HTMLDivElement | null>(null)
let chartInstance: echarts.ECharts | null = null
let resizeObserver: ResizeObserver | null = null

function formatNum(n: number | undefined): string {
  if (n === undefined || n === null) return '0'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(Math.round(n))
}

function calcPercent(part: number, total: number): string {
  if (!total || total <= 0) return '0'
  return Math.min(100, Math.max(0, (part / total) * 100)).toFixed(1)
}

function formatTime(isoStr: string | null | undefined): string {
  if (!isoStr) return '-'
  const d = new Date(isoStr)
  if (isNaN(d.getTime())) return isoStr
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function getKindIcon(kind: string) {
  switch (kind) {
    case 'llm':
      return Cpu
    case 'image':
      return Picture
    case 'tts':
      return Headset
    case 'asr':
      return Microphone
    default:
      return Cpu
  }
}

function getKindIconColor(kind: string): string {
  switch (kind) {
    case 'llm':
      return 'text-indigo-400'
    case 'image':
      return 'text-pink-400'
    case 'tts':
      return 'text-cyan-400'
    case 'asr':
      return 'text-amber-400'
    default:
      return 'text-neutral-400'
  }
}

function getSourceBadgeClass(source: string): string {
  switch (source) {
    case 'classroom':
      return 'bg-violet-500/15 text-violet-500 dark:text-violet-400'
    case 'chat':
      return 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
    case 'agent':
      return 'bg-amber-500/15 text-amber-600 dark:text-amber-400'
    case 'quiz':
      return 'bg-sky-500/15 text-sky-600 dark:text-sky-400'
    default:
      return 'bg-neutral-500/15 text-neutral-400'
  }
}

async function loadData() {
  try {
    await usageStore.fetchDashboard(selectedDays.value, 'all')
    await nextTick()
    renderChart()
  } catch (err) {
    console.error('Failed to load usage dashboard:', err)
    ElMessage.error('加载 Token 消耗看板失败')
  }
}

async function handleSyncClassroom() {
  try {
    const res = await usageStore.syncClassroom()
    ElMessage.success(res?.message || '课堂消耗用量已同步')
    await nextTick()
    renderChart()
  } catch (err) {
    console.error('Failed to sync classroom usage:', err)
    ElMessage.error('同步课堂用量失败')
  }
}

function handleDaysChange() {
  loadData()
}

function handleSourceChange() {
  renderChart()
}

function getWeekday(dateStr: string): string {
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return ''
  const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  return weekdays[d.getDay()]
}

function getPaddedDailyTrend(): UsageDaily[] {
  const raw = usageStore.dailyTrend
  const daysCount = selectedDays.value

  // 获取用户本地的今天（格式：YYYY-MM-DD）
  const today = new Date()
  const formatYMD = (d: Date) => {
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    return `${y}-${m}-${day}`
  }

  // 目标自然日跨度推导：
  // 1. 若选定固定周期 (7 / 30 / 90 天)，则 targetDays 即为 7 / 30 / 90；
  // 2. 若选定 "全部 (0)"：
  //    - 若历史天数不足 7 天（或新用户冷启动），自动以 7 天为基准周保底；
  //    - 若历史天数超过 7 天，则从历史最早记录所在日一直推到今天。
  let targetDays = daysCount > 0 ? daysCount : 7
  if (daysCount === 0 && raw.length > 0) {
    const sortedDates = raw.map(r => r.date).sort()
    const earliestDate = new Date(sortedDates[0])
    if (!isNaN(earliestDate.getTime())) {
      const diffTime = today.getTime() - earliestDate.getTime()
      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1
      targetDays = Math.max(7, diffDays)
    }
  }

  // 构建现有调用数据的快速查找 Map
  const map = new Map<string, UsageDaily>()
  for (const item of raw) {
    map.set(item.date, item)
  }

  // 严格从 (今天 - targetDays + 1) 生成到今天：
  // 当 targetDays = 7 时：i = 6 ... 0，今天在最右边（i = 0），往前推整整 6 个自然日
  const result: UsageDaily[] = []
  for (let i = targetDays - 1; i >= 0; i--) {
    const d = new Date()
    d.setDate(today.getDate() - i)
    const dStr = formatYMD(d)
    if (map.has(dStr)) {
      result.push(map.get(dStr)!)
    } else {
      result.push({
        date: dStr,
        total_tokens: 0,
        chat_tokens: 0,
        classroom_tokens: 0,
        other_tokens: 0,
        requests: 0,
        chat_requests: 0,
        classroom_requests: 0,
        other_requests: 0,
      })
    }
  }
  return result
}

function renderChart() {
  if (!chartRef.value) return
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value, undefined, { renderer: 'svg' })
  }

  const isDark = themeStore.isDark
  const daily = getPaddedDailyTrend()

  const dates = daily.map(d => d.date)
  const isTokens = metricType.value === 'tokens'
  const isLine = chartType.value === 'line'
  const unitLabel = isTokens ? 'Tokens' : '次'

  const totalData = isTokens
    ? daily.map(d => d.total_tokens)
    : daily.map(d => d.requests)

  const classroomData = isTokens
    ? daily.map(d => d.classroom_tokens)
    : daily.map(d => d.classroom_requests ?? (d.classroom_tokens > 0 ? d.requests : 0))

  const chatData = isTokens
    ? daily.map(d => d.chat_tokens)
    : daily.map(d => d.chat_requests ?? (d.chat_tokens > 0 ? d.requests : 0))

  const otherData = isTokens
    ? daily.map(d => d.other_tokens)
    : daily.map(d => d.other_requests ?? 0)

  const axisColor = isDark ? 'rgba(255, 255, 255, 0.45)' : 'rgba(0, 0, 0, 0.45)'
  const splitLineColor = isDark ? 'rgba(255, 255, 255, 0.06)' : 'rgba(0, 0, 0, 0.06)'

  // 根据当前选择的业务来源动态决定展现的系列（独立真实数值，严禁堆叠相加）
  const seriesConfig: any[] = []
  const legendData: string[] = []

  // 全部来源模式下提供清晰的「每日总消耗」对比参考线
  if (selectedSource.value === 'all') {
    legendData.push('每日总消耗')
    seriesConfig.push({
      name: '每日总消耗',
      type: chartType.value,
      smooth: 0.25,
      symbol: 'circle',
      symbolSize: dates.length <= 15 ? 6 : 4,
      showSymbol: dates.length <= 15,
      barMaxWidth: 16,
      barGap: '15%',
      lineStyle: { width: 2.5, color: '#6366f1', type: isLine ? 'dashed' : 'solid' },
      itemStyle: {
        color: '#6366f1',
        borderRadius: !isLine ? [3, 3, 0, 0] : undefined,
      },
      data: totalData,
    })
  }

  if (selectedSource.value === 'all' || selectedSource.value === 'classroom') {
    legendData.push('互动课堂')
    seriesConfig.push({
      name: '互动课堂',
      type: chartType.value,
      smooth: 0.25,
      symbol: 'circle',
      symbolSize: dates.length <= 15 ? 5 : 3,
      showSymbol: dates.length <= 15,
      barMaxWidth: 16,
      barGap: '15%',
      lineStyle: { width: 2, color: '#8b5cf6' },
      itemStyle: {
        color: '#8b5cf6',
        borderRadius: !isLine ? [3, 3, 0, 0] : undefined,
      },
      areaStyle: isLine ? {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: isDark ? 'rgba(139, 92, 246, 0.20)' : 'rgba(139, 92, 246, 0.12)' },
          { offset: 1, color: 'rgba(139, 92, 246, 0.00)' },
        ]),
      } : undefined,
      data: classroomData,
    })
  }

  if (selectedSource.value === 'all' || selectedSource.value === 'chat') {
    legendData.push('AI 问答')
    seriesConfig.push({
      name: 'AI 问答',
      type: chartType.value,
      smooth: 0.25,
      symbol: 'circle',
      symbolSize: dates.length <= 15 ? 5 : 3,
      showSymbol: dates.length <= 15,
      barMaxWidth: 16,
      barGap: '15%',
      lineStyle: { width: 2, color: '#10b981' },
      itemStyle: {
        color: '#10b981',
        borderRadius: !isLine ? [3, 3, 0, 0] : undefined,
      },
      areaStyle: isLine ? {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: isDark ? 'rgba(16, 185, 129, 0.20)' : 'rgba(16, 185, 129, 0.12)' },
          { offset: 1, color: 'rgba(16, 185, 129, 0.00)' },
        ]),
      } : undefined,
      data: chatData,
    })
  }

  if (selectedSource.value === 'all' || selectedSource.value === 'agent') {
    legendData.push('深度研究与其它')
    seriesConfig.push({
      name: '深度研究与其它',
      type: chartType.value,
      smooth: 0.25,
      symbol: 'circle',
      symbolSize: dates.length <= 15 ? 5 : 3,
      showSymbol: dates.length <= 15,
      barMaxWidth: 16,
      barGap: '15%',
      lineStyle: { width: 2, color: '#0ea5e9' },
      itemStyle: {
        color: '#0ea5e9',
        borderRadius: !isLine ? [3, 3, 0, 0] : undefined,
      },
      areaStyle: isLine ? {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: isDark ? 'rgba(14, 165, 233, 0.20)' : 'rgba(14, 165, 233, 0.12)' },
          { offset: 1, color: 'rgba(14, 165, 233, 0.00)' },
        ]),
      } : undefined,
      data: otherData,
    })
  }

  chartInstance.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: isLine ? 'cross' : 'shadow',
        label: { backgroundColor: '#6a7985' },
      },
      formatter: (params: any) => {
        if (!Array.isArray(params) || params.length === 0) return ''
        const dateStr = params[0].axisValue
        const weekdayStr = getWeekday(dateStr)
        let res = `<div style="font-weight:600;margin-bottom:6px;display:flex;justify-content:space-between;gap:16px;">
          <span>${dateStr}</span>
          <span style="font-size:11px;opacity:0.75;font-weight:normal;">${weekdayStr}</span>
        </div>`
        let sum = 0
        for (const p of params) {
          const val = Number(p.value || 0)
          sum += val
          res += `<div style="display:flex;justify-content:space-between;gap:16px;font-size:12px;margin:3px 0;">
            <span>${p.marker} ${p.seriesName}</span>
            <span style="font-family:monospace;font-weight:600;">${formatNum(val)} <span style="font-size:10px;font-weight:normal;opacity:0.75;">${unitLabel}</span></span>
          </div>`
        }
        res += `<div style="margin-top:6px;padding-top:4px;border-top:1px solid ${isDark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.15)'};display:flex;justify-content:space-between;gap:16px;font-size:12px;font-weight:600;">
          <span>当日总计</span>
          <span style="font-family:monospace;">${formatNum(sum)} <span style="font-size:10px;font-weight:normal;">${unitLabel}</span></span>
        </div>`
        return res
      },
    },
    legend: {
      data: legendData,
      top: 0,
      right: 8,
      textStyle: { color: axisColor, fontSize: 11 },
    },
    grid: {
      left: 54,
      right: 20,
      top: 36,
      bottom: 26,
    },
    xAxis: {
      type: 'category',
      boundaryGap: !isLine,
      data: dates,
      axisLabel: {
        color: axisColor,
        fontSize: 10,
        formatter: (val: string) => (val && val.length >= 10 ? val.slice(5) : val),
      },
      axisLine: { lineStyle: { color: splitLineColor } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        color: axisColor,
        fontSize: 10,
        formatter: (val: number) => formatNum(val),
      },
      splitLine: { lineStyle: { color: splitLineColor } },
    },
    series: seriesConfig,
  }, true)
}

function handleResize() {
  chartInstance?.resize()
}

watch(
  () => themeStore.isDark,
  () => {
    renderChart()
  }
)

watch(
  () => usageStore.dailyTrend,
  () => {
    nextTick(() => {
      renderChart()
    })
  },
  { deep: true }
)

onMounted(async () => {
  await loadData()
  if (chartRef.value) {
    resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect.width > 0) {
          if (!chartInstance) {
            renderChart()
          } else {
            chartInstance.resize()
          }
        }
      }
    })
    resizeObserver.observe(chartRef.value)
  }
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
  chartInstance = null
})
</script>
