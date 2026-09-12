<template>
  <div class="card p-5" data-test="learning-activity">
    <div class="flex items-start justify-between gap-3 mb-4">
      <div>
        <h3 class="text-sm font-semibold text-[var(--text-primary)]">学习活动</h3>
        <p class="text-xs text-[var(--text-muted)] mt-0.5">
          近 {{ days }} 天 · {{ total }} 次学习行为 · {{ activeDays }} 天活跃
        </p>
      </div>
      <div class="flex items-center gap-1.5 text-[10px] text-[var(--text-muted)] shrink-0">
        <span>少</span>
        <span
          v-for="lv in 5"
          :key="lv"
          class="w-2.5 h-2.5 rounded-[3px] border border-[var(--border-default)]"
          :style="levelStyle(lv - 1)"
        />
        <span>多</span>
      </div>
    </div>

    <div class="overflow-x-auto pb-1">
      <div class="inline-flex flex-col gap-1 min-w-full">
        <!-- 月份标签 -->
        <div v-if="monthLabels.length" class="flex" :style="{ gap: gapPx + 'px', paddingLeft: dayLabelWidth }">
          <div
            v-for="(m, i) in monthLabels"
            :key="i"
            class="h-3 shrink-0 text-[10px] leading-none text-[var(--text-muted)]"
            :style="{ width: cellPx + 'px' }"
          >
            {{ m }}
          </div>
        </div>

        <div class="flex" :style="{ gap: gapPx + 'px' }">
          <!-- 周几标签 -->
          <div
            class="flex flex-col shrink-0"
            :style="{ gap: gapPx + 'px', width: dayLabelWidth }"
          >
            <div
              v-for="(lab, i) in dayLabels"
              :key="i"
              class="text-[10px] leading-none text-[var(--text-muted)] flex items-center"
              :style="{ height: cellPx + 'px' }"
            >
              {{ lab }}
            </div>
          </div>

          <!-- 周列 -->
          <div
            v-for="(week, wi) in weeks"
            :key="wi"
            class="flex flex-col shrink-0"
            :style="{ gap: gapPx + 'px' }"
          >
            <div
              v-for="(day, di) in week"
              :key="day?.date || wi + '-' + di"
              class="rounded-[3px] border border-[var(--border-default)] cursor-default"
              :style="{
                width: cellPx + 'px',
                height: cellPx + 'px',
                ...(day ? levelStyle(day.level) : emptyStyle)
              }"
              :title="day ? describeDay(day) : undefined"
              @pointerenter="onHover(day, $event)"
              @pointerleave="hovered = null"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- 浮层提示 -->
    <Teleport to="body">
      <div
        v-if="hovered"
        class="pointer-events-none fixed z-50 -translate-x-1/2 -translate-y-full px-2 py-1 rounded-lg text-[11px] font-medium shadow-md whitespace-nowrap"
        :style="{
          left: hovered.x + 'px',
          top: hovered.y - 8 + 'px',
          backgroundColor: 'var(--text-primary)',
          color: 'var(--bg-primary)',
        }"
        data-test="activity-tooltip"
      >
        {{ describeDay(hovered.day) }}
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import api from '@/services/api'

export type Contribution = {
  date: string
  count: number
  level: number
}

const props = withDefaults(
  defineProps<{
    days?: number
    cellSize?: number
  }>(),
  {
    days: 365,
    cellSize: 11,
  }
)

const contributions = ref<Contribution[]>([])
const total = ref(0)
const activeDays = ref(0)
const hovered = ref<{ day: Contribution; x: number; y: number } | null>(null)

const cellPx = computed(() => props.cellSize)
const gapPx = computed(() => Math.max(2, Math.round(props.cellSize / 4)))
const dayLabelWidth = '22px'

const dayLabels = ['', '一', '', '三', '', '五', '']

const emptyStyle = { backgroundColor: 'transparent' }

function levelStyle(level: number): Record<string, string> {
  // 设计令牌：主色在亮/暗下自动反转；用透明度分档
  const opacity = [0, 0.22, 0.42, 0.68, 1][Math.min(4, Math.max(0, level))]
  if (level <= 0) {
    return { backgroundColor: 'var(--bg-tertiary)', opacity: '1' }
  }
  return { backgroundColor: 'var(--color-primary)', opacity: String(opacity) }
}

function describeDay(day: Contribution): string {
  const d = new Date(day.date + 'T00:00:00')
  const label = `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
  if (!day.count) return `${label}：无学习记录`
  return `${label}：${day.count} 次学习`
}

const weeks = computed(() => {
  const list = contributions.value
  if (!list.length) return []
  // 对齐到周日为一列起点
  let startIdx = 0
  const first = new Date(list[0].date + 'T00:00:00')
  startIdx = first.getDay()
  const padded: (Contribution | null)[] = [
    ...Array.from({ length: startIdx }, () => null),
    ...list,
  ]
  const out: (Contribution | null)[][] = []
  for (let i = 0; i < padded.length; i += 7) {
    const week = padded.slice(i, i + 7)
    while (week.length < 7) week.push(null)
    out.push(week)
  }
  return out
})

const monthLabels = computed(() => {
  const cols = weeks.value
  const labels: (string | null)[] = cols.map(() => null)
  const names = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']
  const monthAt = (i: number) => cols[i]?.find(d => d)?.date.slice(5, 7)
  let start = 0
  for (let i = 1; i <= cols.length; i++) {
    if (i < cols.length && monthAt(i) === monthAt(start)) continue
    if (i - start >= 3 && monthAt(start)) {
      labels[start] = names[Number(monthAt(start)) - 1] ?? null
    }
    start = i
  }
  return labels
})

function onHover(day: Contribution | null, e: PointerEvent) {
  if (!day) return
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  hovered.value = {
    day,
    x: rect.left + rect.width / 2,
    y: rect.top,
  }
}

async function load() {
  try {
    const res = await api.get('/analysis/activity', { params: { days: props.days } })
    const data = res.data
    contributions.value = Array.isArray(data?.contributions) ? data.contributions : []
    total.value = data?.total ?? 0
    activeDays.value = data?.active_days ?? 0
  } catch {
    contributions.value = []
  }
}

onMounted(load)
</script>
