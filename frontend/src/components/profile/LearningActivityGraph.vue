<template>
  <div
    class="relative max-w-full overflow-hidden rounded-[28px] bg-white p-4 dark:bg-black"
    data-test="learning-activity"
    :style="{ minWidth: minCardWidth + 'px' }"
  >
    <p class="mb-4 px-1.5 text-base font-medium text-[var(--text-primary)]">
      {{ heading }}
    </p>

    <div class="overflow-x-auto pb-1">
      <div class="flex justify-center" :style="{ gap: gapPx + 'px', marginBottom: gapPx + 'px' }">
        <div
          v-for="(month, index) in monthLabels"
          :key="index"
          class="relative h-3 shrink-0"
          :style="{ width: cellPx + 'px' }"
        >
          <span
            v-if="month"
            class="absolute left-0 top-0 text-[10px] leading-none text-[var(--text-muted)]"
          >
            {{ month }}
          </span>
        </div>
      </div>

      <div
        class="flex justify-center overflow-hidden"
        :style="{ gap: gapPx + 'px' }"
        @pointerleave="hovered = null"
      >
        <div
          v-for="(week, weekIndex) in weeks"
          :key="weekIndex"
          class="flex flex-col"
          :style="{ gap: gapPx + 'px' }"
        >
          <div
            v-for="day in week"
            :key="day.date"
            class="activity-cell shrink-0 rounded-[3px] cursor-default"
            data-test="activity-cell"
            :style="{ width: cellPx + 'px', height: cellPx + 'px' }"
            :title="describeDay(day)"
            @pointerenter="onHover(day, $event)"
          >
            <!-- 叠层：贡献色 + 透明度；level 0 仅露灰底 -->
            <div
              class="h-full w-full rounded-[3px]"
              data-test="activity-level"
              :style="levelOverlay(day.level)"
            />
          </div>
        </div>
      </div>
    </div>

    <Teleport to="body">
      <div
        v-if="hovered"
        class="pointer-events-none fixed z-50 -translate-x-1/2 -translate-y-full"
        :style="{ left: hovered.x + 'px', top: hovered.y + 'px' }"
        data-test="activity-tooltip"
      >
        <div
          class="whitespace-nowrap rounded-lg px-2 py-1 text-[11px] font-medium shadow-md"
          :style="{
            backgroundColor: 'var(--text-primary)',
            color: 'var(--bg-primary)',
          }"
        >
          {{ describeDay(hovered.day) }}
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import api from '@/services/api'

/** 对齐 rare-ui/github-activity：灰底格 + 贡献色透明度叠层 */
export type ContributionLevel = 0 | 1 | 2 | 3 | 4

export type Contribution = {
  date: string
  count: number
  level: ContributionLevel
}

const props = withDefaults(
  defineProps<{
    days?: number
    cellSize?: number
    accent?: string
  }>(),
  {
    days: 365,
    cellSize: 11,
    // 原组件 DEFAULT_ACCENT
    accent: '#39d353',
  }
)

const LEVEL_OPACITY: Record<ContributionLevel, number> = {
  0: 0,
  1: 0.3,
  2: 0.52,
  3: 0.76,
  4: 1,
}

const MIN_CARD_WIDTH = 320
const CARD_PADDING = 32

const loaded = ref<Contribution[]>([])
const total = ref(0)
const activeDays = ref(0)
const hovered = ref<{ day: Contribution; x: number; y: number } | null>(null)

const cellPx = computed(() => props.cellSize)
const gapPx = computed(() => Math.max(2, Math.round(props.cellSize / 4)))
const minCardWidth = MIN_CARD_WIDTH

/** 无数据时也铺满灰格（对齐原组件 emptyDays） */
function emptyDays(days: number): Contribution[] {
  const today = new Date()
  return Array.from({ length: days }, (_, i) => {
    const date = new Date(today)
    date.setDate(date.getDate() - (days - 1 - i))
    const iso = date.toISOString().slice(0, 10)
    return { date: iso, count: 0, level: 0 as ContributionLevel }
  })
}

const contributions = computed<Contribution[]>(() => {
  if (loaded.value.length) return loaded.value
  return emptyDays(props.days)
})

const weeks = computed(() => {
  const list = contributions.value
  // 对齐周日为一列起点（原组件 fetchCalendar 同样对齐 Sunday）
  let startIdx = 0
  if (list.length) {
    startIdx = new Date(list[0].date + 'T00:00:00Z').getUTCDay()
    if (startIdx < 0) startIdx = 0
  }
  const padded: Contribution[] = Array.from({ length: startIdx }, (_, i) => {
    const d = new Date(list[0].date + 'T00:00:00Z')
    d.setUTCDate(d.getUTCDate() - (startIdx - i))
    const iso = d.toISOString().slice(0, 10)
    return { date: iso, count: 0, level: 0 as ContributionLevel }
  }).concat(list)

  const out: Contribution[][] = []
  for (let i = 0; i < padded.length; i += 7) {
    out.push(padded.slice(i, i + 7))
  }
  return out
})

const MONTH_NAMES = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']

const monthLabels = computed(() => {
  const cols = weeks.value
  const labels: (string | null)[] = cols.map(() => null)
  const monthAt = (i: number) => cols[i]?.[0]?.date.slice(5, 7)
  let start = 0
  for (let i = 1; i <= cols.length; i++) {
    if (i < cols.length && monthAt(i) === monthAt(start)) continue
    if (i - start >= 3 && monthAt(start)) {
      labels[start] = MONTH_NAMES[Number(monthAt(start)) - 1] ?? null
    }
    start = i
  }
  return labels
})

function levelOverlay(level: number): { backgroundColor: string; opacity: number } {
  const lv = (Math.min(4, Math.max(0, level)) as ContributionLevel)
  return {
    backgroundColor: props.accent,
    opacity: LEVEL_OPACITY[lv],
  }
}

const heading = computed(() => {
  const list = contributions.value
  const year = list.length ? list[list.length - 1].date.slice(0, 4) : ''
  const y = year ? ` in ${year}` : ''
  return `${total.value} contributions${y}`
})

const widthHint = computed(() => {
  const columns = Math.max(1, Math.ceil(contributions.value.length / 7))
  return Math.max(MIN_CARD_WIDTH, columns * (cellPx.value + gapPx.value) - gapPx.value + CARD_PADDING)
})
// 宽度在 overflow-x 容器内自然伸展；minWidth 保证卡片形态
void widthHint

function describeDay(day: Contribution): string {
  const noun = day.count === 1 ? 'contribution' : 'contributions'
  const d = new Date(day.date + 'T00:00:00')
  const fmt = `${d.toLocaleString('en-US', { month: 'short' })} ${d.getDate()}, ${d.getFullYear()}`
  return `${day.count} ${noun} on ${fmt}`
}

function onHover(day: Contribution, e: PointerEvent) {
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  hovered.value = { day, x: rect.left + rect.width / 2, y: rect.top }
}

async function load() {
  try {
    const res = await api.get('/analysis/activity', { params: { days: props.days } })
    const data = res.data
    loaded.value = Array.isArray(data?.contributions)
      ? data.contributions.map((d: any) => ({
          date: d.date,
          count: Number(d.count) || 0,
          level: Math.min(4, Math.max(0, Number(d.level) || 0)) as ContributionLevel,
        }))
      : []
    total.value = data?.total ?? 0
    activeDays.value = data?.active_days ?? 0
  } catch {
    loaded.value = []
  }
}

onMounted(load)
</script>

<style scoped>
/* 对齐 rare-ui / GitHub：空格恒为浅灰底，贡献用绿色叠层透明度 */
.activity-cell {
  background-color: rgba(27, 31, 35, 0.08);
}
html.dark .activity-cell {
  background-color: rgba(255, 255, 255, 0.08);
}
</style>
