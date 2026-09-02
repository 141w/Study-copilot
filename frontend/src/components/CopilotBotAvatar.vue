<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, shallowRef, watch } from 'vue'
import { BotEngine, type BotFrame } from '@/bot/engine'
import { SHAPE_BY_ID, DEFAULT_SHAPE } from '@/bot/skins'
import { EXPRESSION_BY_ID, DEFAULT_EXPRESSION } from '@/bot/expressions'
import { RAYON, DEMI_VIEWBOX } from '@/bot/repere'
import { type Block } from '@/bot/cycles'

export type BotMood = 'idle' | 'acknowledge' | 'thinking' | 'answering' | 'done'

const props = withDefaults(
  defineProps<{
    isStreaming?: boolean
    /** 渲染尺寸（px），正方形 */
    size?: number
    mood?: BotMood
  }>(),
  { isStreaming: false, size: 32, mood: 'idle' }
)

const R = RAYON
const VB = DEMI_VIEWBOX
const maskId = 'cba-' + Math.random().toString(36).slice(2, 8)

const shapeRadii = computed(() => SHAPE_BY_ID.get(DEFAULT_SHAPE)?.radii ?? null)
const expression = computed(() => EXPRESSION_BY_ID.get(DEFAULT_EXPRESSION) ?? null)

const engine = new BotEngine(R, 'idle', shapeRadii.value, expression.value)
const frame = shallowRef<BotFrame>(engine.sample(0))

let raf = 0
let clock = 0
let last = 0
let currentBlock = 0
let cycleComplete = false

function moodBlocks(mood: BotMood): Block[] {
  switch (mood) {
    case 'idle':
      return [{ state: 'idle', duration: 12 }]
    case 'acknowledge':
      return [
        { state: 'idle', duration: 0.4 },
        { state: 'notify', duration: 1.2 },
        { state: 'idle', duration: 0.8 },
      ]
    case 'thinking':
      return [
        { state: 'idle', duration: 1.5 },
        { state: 'alert', duration: 2.0 },
        { state: 'idle', duration: 0.8 },
        { state: 'wink', duration: 0.6 },
      ]
    case 'answering':
      return [
        { state: 'idle', duration: 1.0 },
        { state: 'wide', duration: 2.5 },
        { state: 'notify', duration: 1.5 },
        { state: 'idle', duration: 1.0 },
      ]
    case 'done':
      return [
        { state: 'idle', duration: 0.5 },
        { state: 'wink', duration: 1.5 },
        { state: 'idle', duration: 2.0 },
      ]
  }
}

const loopingMoods: BotMood[] = ['idle', 'thinking', 'answering']

function tick(ms: number): void {
  raf = requestAnimationFrame(tick)
  // 页面不可见时挂起（长会话 N 个头像 × rAF 的成本在切后台时归零）；
  // 恢复时 last 重置，避免 dt 突变跳帧
  if (document.hidden) { last = 0; return }
  const dt = last ? Math.min((ms - last) / 1000, 0.064) : 0
  last = ms
  clock += dt

  // 每帧只读一次 blocks（原每帧两次 reduce + includes）
  const blocks = moodBlocks(props.mood)
  const isLooping = loopingMoods.includes(props.mood)
  const total = blocks.reduce((s, b) => s + b.duration, 0)
  if (total <= 0) return

  const t = isLooping ? clock % total : clock
  // 一次性 mood（acknowledge/done）播完回到 idle 持续呼吸。
  // 修复：done 原本播完直接冻结在最后一帧（acknowledge 有回落、done 没有），
  // 且 doneTimer 声明后从未赋值（死代码，已删）。
  if (!isLooping && clock >= total && !cycleComplete) {
    cycleComplete = true
    currentBlock = 0
    engine.setState('idle', clock)
    frame.value = engine.sample(clock)
    return
  }
  // 一次性 mood 播完后：clock 继续走，但时间轴保持在 idle 的持续动画上
  const effT = (!isLooping && cycleComplete) ? clock - total : t

  let acc = 0
  for (let i = 0; i < blocks.length; i++) {
    const end = acc + blocks[i].duration
    if (effT < end) {
      if (currentBlock !== i) {
        currentBlock = i
        engine.setState(blocks[i].state, clock)
      }
      break
    }
    acc = end
  }
  // 播完的一次性 mood：始终落在 idle（blocks 最后一块）
  if (!isLooping && cycleComplete) {
    if (currentBlock !== blocks.length - 1) {
      currentBlock = blocks.length - 1
      engine.setState(blocks[blocks.length - 1].state, clock)
    }
  }

  frame.value = engine.sample(clock)
}

function reset(): void {
  clock = 0
  last = 0
  currentBlock = 0
  cycleComplete = false
  engine.setState('idle', 0)
  frame.value = engine.sample(0)
}

watch(() => props.mood, () => { reset() })

onMounted(() => { reset(); raf = requestAnimationFrame(tick) })
onBeforeUnmount(() => { cancelAnimationFrame(raf) })
</script>

<template>
  <svg
    :width="size"
    :height="size"
    :viewBox="'-' + VB + ' -' + VB + ' ' + (VB * 2) + ' ' + (VB * 2)"
    role="img"
    aria-label="Study Copilot"
    class="flex-shrink-0"
    style="overflow: visible"
  >
    <defs>
      <linearGradient id="ink-grad" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="var(--color-brand-from, #4F6EF7)" />
        <stop offset="100%" stop-color="var(--color-brand-to, #7B61FF)" />
      </linearGradient>

      <mask :id="maskId" maskUnits="userSpaceOnUse" :x="-VB" :y="-VB" :width="VB * 2" :height="VB * 2">
        <path :d="frame.bodyPath" fill="#fff" />
        <path
          v-for="(eye, i) in frame.eyes"
          :key="i"
          :d="eye.d"
          :transform="eye.matrix"
          :opacity="eye.alpha"
          fill="#000"
        />
      </mask>

      <linearGradient
        v-for="arc in frame.arcs"
        :id="maskId + '-' + arc.id"
        :key="arc.id"
        gradientUnits="userSpaceOnUse"
        :x1="arc.grad.x1"
        :y1="arc.grad.y1"
        :x2="arc.grad.x2"
        :y2="arc.grad.y2"
      >
        <stop
          v-for="(c, ci) in arc.grad.stops"
          :key="ci"
          :offset="String(ci / (arc.grad.stops.length - 1))"
          :stop-color="c"
        />
      </linearGradient>
    </defs>

    <!-- Arcs behind body -->
    <g fill="none" stroke-linecap="round">
      <path
        v-for="arc in frame.arcs"
        :key="'b' + arc.id"
        :d="arc.back"
        :stroke="'url(#' + maskId + '-' + arc.id + ')'"
        :stroke-width="arc.width"
        :opacity="arc.opacity"
      />
    </g>

    <!-- Body with eye holes -->
    <g :opacity="frame.bodyAlpha">
      <path :d="frame.bodyPath" fill="var(--bg-secondary, #f5f5f5)" />
      <g :mask="'url(#' + maskId + ')'">
        <rect :x="-VB" :y="-VB" :width="VB * 2" :height="VB * 2" fill="url(#ink-grad)" />
      </g>
    </g>

    <!-- Front arcs -->
    <g fill="none" stroke-linecap="round">
      <path
        v-for="arc in frame.arcs"
        :key="'f' + arc.id"
        :d="arc.front"
        :stroke="'url(#' + maskId + '-' + arc.id + ')'"
        :stroke-width="arc.width"
        :opacity="arc.opacity"
      />
    </g>
  </svg>
</template>
