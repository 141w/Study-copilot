<script setup lang="ts">
/**
 * CopilotBotAvatar（P8 全面接线版）
 *
 * bloub 引擎的完整客户端：15 个状态中编排 12 个、16 表情按 mood 换脸、
 * 指针注视跟随（gaze.ts 规则）。引擎契约不变：sample(t) 纯函数、
 * 外部状态只经 setter 进（setLook/setExpression/setState）。
 *
 * reduced-motion 分界沿用 bloub 的哲学：注视/装饰态（orbit/burst/comet/play
 * 这类大戏）跳过，呼吸、眨眼、漂移保留——那三样是球的本体。
 */
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, triggerRef, watch } from 'vue'
import { BotEngine, type BotFrame } from '@/bot/engine'
import { SHAPE_BY_ID, DEFAULT_SHAPE } from '@/bot/skins'
import { EXPRESSION_BY_ID, type ExpressionId } from '@/bot/expressions'
import { RAYON, DEMI_VIEWBOX } from '@/bot/repere'
import { type Block } from '@/bot/cycles'
import { lookTarget } from '@/bot/gaze'
import { NOTIF_BLUE } from '@/bot/decor'
import { useUserPrefs } from '@/composables/useUserPrefs'

const emit = defineEmits<{ interact: [mood: BotMood] }>()

/** 一次性场景动画的时长（ms）：到点恢复 idle 呼吸 */
const SCENE_MS: Partial<Record<BotMood, number>> = {
  acknowledge: 2500,
  exclaim: 4200,
  cancelled: 4200,
  comet: 4800,
  burst: 5000,
  arrive: 6000
}

/**
 * Mood 目录（场景 → 状态编排）。
 * thinking 语义细分：egg = 等首 token，thinking = bloub 真版三点（替代旧 alert 凑数）。
 */
export type BotMood =
  | 'idle'
  | 'acknowledge'
  | 'thinking'
  | 'answering'
  | 'done'
  /** 等待首 token（蛋形收紧） */
  | 'egg'
  /** 错误（"！" 竖立造型） */
  | 'exclaim'
  /** 用户中止流式（眨眼示意"好吧"） */
  | 'cancelled'
  /** 空闲打瞌睡（循环） */
  | 'sleep'
  /** 新会话/会话载入入场大戏（orbit 3.4s） */
  | 'arrive'
  /** 清空会话（粒子爆散重组） */
  | 'burst'
  /** 导出/长任务完成（彗尾飘移） */
  | 'comet'

const { prefs } = useUserPrefs()

const props = withDefaults(
  defineProps<{
    isStreaming?: boolean
    /** 渲染尺寸（px），正方形 */
    size?: number
    mood?: BotMood
    /** 表情（默认 neutre；thinking/answering 等可指定惊/喜等） */
    expression?: ExpressionId
    /** 指针注视跟随（未指定时跟随全局用户偏好） */
    gaze?: boolean
  }>(),
  { isStreaming: false, size: 32, mood: 'idle', expression: 'neutre', gaze: undefined }
)

const effectiveGaze = computed(() => {
  if (props.isStreaming) return false
  return props.gaze !== undefined ? props.gaze : (prefs.value.botGaze ?? true)
})

const R = RAYON
const VB = DEMI_VIEWBOX
const maskId = 'cba-' + Math.random().toString(36).slice(2, 8)

const rootEl = ref<SVGSVGElement | null>(null)
const shapeRadii = computed(() => SHAPE_BY_ID.get(DEFAULT_SHAPE)?.radii ?? null)

const engine = new BotEngine(R, 'idle', shapeRadii.value, null)
const frame = shallowRef<BotFrame>(engine.sample(0))

let raf = 0
let clock = 0
let last = 0
let currentBlock = 0
let cycleComplete = false
let sceneTimer: ReturnType<typeof setTimeout> | null = null

/** 热插拔的一次性场景：tick() 优先于 props.mood 使用它 */
let sceneOverride: Block[] | null = null

/** reduced-motion：动态读取（bloub 契约——运行时跟随，非一次性读取） */
const mql = typeof window !== 'undefined' && typeof window.matchMedia === 'function'
  ? window.matchMedia('(prefers-reduced-motion: reduce)')
  : null
const prefersReduced = () => mql?.matches ?? false

/**
 * mood → 状态块编排。时长自 states.ts 的测量值或其倍数；
 * 循环 mood 只含可循环的呼吸类（idle/sleep）。
 */
function moodBlocks(mood: BotMood): Block[] {
  switch (mood) {
    case 'idle':
      return [{ state: 'idle', duration: 12 }]
    case 'acknowledge':
      return [
        { state: 'idle', duration: 0.4 },
        { state: 'notify', duration: 1.2 },
        { state: 'idle', duration: 0.8 }
      ]
    case 'thinking':
      // bloub 真版三点：球 morph 为中间点，两侧点从球侧浮现（与消息流的
      // thinking-dot CSS 脉冲是同一视觉语言）
      return [
        { state: 'idle', duration: 0.5 },
        { state: 'thinking', duration: 2.6 },
        { state: 'idle', duration: 0.6 },
        { state: 'thinking', duration: 2.6 }
      ]
    case 'egg':
      return [
        { state: 'idle', duration: 0.4 },
        { state: 'egg', duration: 1.8 },
        { state: 'idle', duration: 0.6 }
      ]
    case 'answering':
      return [
        { state: 'idle', duration: 1.0 },
        { state: 'wide', duration: 2.5 },
        { state: 'notify', duration: 1.5 },
        { state: 'idle', duration: 1.0 }
      ]
    case 'done':
      // 完成轻快收尾：wink + play（三角扫过）
      return [
        { state: 'idle', duration: 0.5 },
        { state: 'wink', duration: 1.5 },
        { state: 'play', duration: 2.0 },
        { state: 'idle', duration: 2.0 }
      ]
    case 'exclaim':
      return [
        { state: 'idle', duration: 0.3 },
        { state: 'exclaim', duration: 2.0 },
        { state: 'idle', duration: 1.5 }
      ]
    case 'cancelled':
      return [
        { state: 'idle', duration: 0.3 },
        { state: 'wink', duration: 1.6 },
        { state: 'idle', duration: 2.0 }
      ]
    case 'sleep':
      return [
        { state: 'idle', duration: 1.2 },
        { state: 'sleep', duration: 3.0 },
        { state: 'idle', duration: 0.8 }
      ]
    case 'arrive':
      return [
        { state: 'idle', duration: 0.6 },
        { state: 'orbit', duration: 3.4 },
        { state: 'idle', duration: 1.5 }
      ]
    case 'burst':
      return [
        { state: 'idle', duration: 0.4 },
        { state: 'burst', duration: 2.6 },
        { state: 'idle', duration: 1.5 }
      ]
    case 'comet':
      return [
        { state: 'idle', duration: 0.4 },
        { state: 'comet', duration: 2.4 },
        { state: 'idle', duration: 1.5 }
      ]
  }
}

/** 热插拔一次性子场景：覆盖 props.mood，到点恢复 */
function playScene(mood: BotMood): void {
  if (props.isStreaming) return
  if (sceneTimer) clearTimeout(sceneTimer)
  sceneOverride = moodBlocks(mood)
  clock = 0; currentBlock = 0; cycleComplete = false
  // 取场景第一个 state 归位引擎
  const first = sceneOverride[0]
  if (first) engine.setState(first.state, 0)
  sceneTimer = setTimeout(() => {
    sceneOverride = null; sceneTimer = null
    clock = 0; currentBlock = 0; cycleComplete = false
    engine.setState('idle', 0)
  }, SCENE_MS[mood] ?? 2500)
}

/** 循环 mood：时间轴取模循环播放（呼吸类/瞌睡类） */
const loopingMoods: BotMood[] = ['idle', 'thinking', 'answering', 'egg', 'sleep']

/**
 * 装饰性大戏（一次性事件）：reduced-motion 下整段跳过——
 * 直接停在 idle 呼吸，不损失信息（这些是庆祝/仪式，不是状态表达）。
 */
const decorativeMoods: BotMood[] = ['arrive', 'burst', 'comet', 'done', 'acknowledge', 'exclaim', 'cancelled']

function effectiveMood(): BotMood {
  if (props.isStreaming) return 'thinking'
  if (prefersReduced() && decorativeMoods.includes(props.mood)) return 'idle'
  return props.mood
}

/* ---------------- 指针注视（gaze.ts 规则） ---------------- */

let pointer: { x: number; y: number } | null = null

function onPointerMove(e: PointerEvent): void {
  pointer = { x: e.clientX, y: e.clientY }
}

function onPointerLeave(): void {
  pointer = null
}

/**
 * 每帧把指针位置换算成注视目标（bloub aim 契约）。
 * 零面积 rect 直接返回：NaN 一旦 setLook 会被引擎永久记住（真实事故）。
 * 混合交给引擎——只有它知道 t 时刻的 pose；这里补偿表情会重蹈眼睛跳变坑。
 */
function aim(): void {
  if (!effectiveGaze.value || prefersReduced() || !rootEl.value) {
    if (rootEl.value) {
      engine.setLook(lookTarget({ nx: 0, ny: 0, pointer: false }), clock)
    }
    return
  }
  const box = rootEl.value.getBoundingClientRect()
  if (!box || box.width === 0 || box.height === 0) return
  const demiW = Math.max(1, window.innerWidth / 2)
  const demiH = Math.max(1, window.innerHeight / 2)
  const nx = pointer ? (pointer.x - (box.left + box.width / 2)) / demiW : 0
  const ny = pointer ? (pointer.y - (box.top + box.height / 2)) / demiH : 0
  engine.setLook(
    lookTarget({
      nx: Number.isFinite(nx) ? Math.max(-1, Math.min(1, nx)) : 0,
      ny: Number.isFinite(ny) ? Math.max(-1, Math.min(1, ny)) : 0,
      pointer: pointer !== null
    }),
    clock
  )
}

/* ---------------- 主循环 ---------------- */

function tick(ms: number): void {
  raf = requestAnimationFrame(tick)
  // 页面不可见时挂起（长会话成本在切后台时归零）；恢复时 last 归零防 dt 跳帧
  if (document.hidden) { last = 0; return }
  const dt = last ? Math.min((ms - last) / 1000, 0.064) : 0
  last = ms
  clock += dt

  const mood = effectiveMood()
  const blocks = sceneOverride ?? moodBlocks(mood)
  const isLooping = sceneOverride ? false : loopingMoods.includes(mood)
  const total = blocks.reduce((s, b) => s + b.duration, 0)
  if (total <= 0) return

  const t = clock
  if (!isLooping && !sceneOverride && clock >= total && !cycleComplete) {
    cycleComplete = true
    currentBlock = 0
    engine.setState('idle', clock)
    frame.value = engine.sample(clock)
    return
  }
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
  if (!isLooping && cycleComplete) {
    if (currentBlock !== blocks.length - 1) {
      currentBlock = blocks.length - 1
      engine.setState(blocks[blocks.length - 1].state, clock)
    }
  }

  aim()
  frame.value = engine.sample(clock)
  triggerRef(frame)
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

/** 表情切换：引擎内走 morph（SHAPE_MORPH 0.45s），不重置时钟 */
watch(() => props.expression, (id) => {
  engine.setExpression(EXPRESSION_BY_ID.get(id) ?? null, clock)
})

onMounted(() => {
  reset()
  engine.setExpression(EXPRESSION_BY_ID.get(props.expression) ?? null, 0)
  window.addEventListener('pointermove', onPointerMove, { passive: true })
  document.addEventListener('pointerleave', onPointerLeave)
  raf = requestAnimationFrame(tick)
})
onBeforeUnmount(() => {
  cancelAnimationFrame(raf)
  window.removeEventListener('pointermove', onPointerMove)
  document.removeEventListener('pointerleave', onPointerLeave)
  if (sceneTimer) clearTimeout(sceneTimer)
})

watch(() => props.isStreaming, (streaming) => {
  if (streaming) {
    if (sceneTimer) {
      clearTimeout(sceneTimer)
      sceneTimer = null
    }
    sceneOverride = null
    reset()
  }
})

/** 触碰球体——优先点头承认，通知父组件也可以响应 */
function onBotInteract(): void {
  if (props.isStreaming) return
  playScene('acknowledge')
  emit('interact', 'acknowledge')
}

defineExpose({ play: playScene })

/**
 * 装饰点属性（移植 bloub dotAttrs）：d path 是球半径单位的原点路径，
 * 用 translate/rotate/scale(R) 摆位。Study Copilot 墨色统一品牌渐变。
 */
function dotAttrs(dot: BotFrame['dots'][number]): Record<string, string | number> {
  const common: Record<string, string | number> = { opacity: dot.opacity, fill: 'url(#ink-grad)' }
  if (dot.d) {
    common.d = dot.d
    common.transform = 'translate(' + dot.x + ' ' + dot.y + ') rotate(' + (dot.rot ?? 0) + ') scale(' + R + ')'
  } else {
    common.cx = dot.x
    common.cy = dot.y
    common.r = dot.r
  }
  return common
}
</script>

<template>
  <svg
    ref="rootEl"
    :width="size"
    :height="size"
    :viewBox="'-' + VB + ' -' + VB + ' ' + (VB * 2) + ' ' + (VB * 2)"
    role="img"
    aria-label="Study Copilot"
    class="flex-shrink-0"
    :class="isStreaming ? 'cursor-default pointer-events-none' : 'cursor-pointer'"
    style="overflow: visible"
    @pointerenter="onBotInteract"
  >
    <defs>
      <linearGradient id="ink-grad" x1="0" y1="0" x2="1" y2="1">
        <!-- 兜底 hex 对齐黑白品牌 token（DESIGN.md 单色系），防 token 缺失时露出异色 -->
        <stop offset="0%" stop-color="var(--color-brand-from, #000000)" />
        <stop offset="100%" stop-color="var(--color-brand-to, #3f3f44)" />
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
        <!-- notify 挖槽：蓝点嵌进轮廓的缺口 -->
        <circle v-if="frame.notch" :cx="frame.notch.x" :cy="frame.notch.y" :r="frame.notch.r" fill="#000" />
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

    <!-- Arcs behind body（爆散粒子 dotsBehind=true 时走此层） -->
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

    <!-- burst 粒子（走球后，被身体遮挡产生纵深） -->
    <g v-if="frame.dotsBehind">
      <component
        :is="dot.d ? 'path' : 'circle'"
        v-for="(dot, i) in frame.dots"
        :key="'pb' + i"
        v-bind="dotAttrs(dot)"
      />
    </g>

    <!-- Body with eye holes -->
    <g :opacity="frame.bodyAlpha">
      <path :d="frame.bodyPath" fill="var(--bg-secondary, #f5f5f5)" />
      <g :mask="'url(#' + maskId + ')'">
        <rect :x="-VB" :y="-VB" :width="VB * 2" :height="VB * 2" fill="url(#ink-grad)" />
      </g>
    </g>

    <!-- 前景 dots（thinking 三点 / alert 泪滴 / burst 前排碎片） -->
    <g v-if="!frame.dotsBehind">
      <component
        :is="dot.d ? 'path' : 'circle'"
        v-for="(dot, i) in frame.dots"
        :key="'pf' + i"
        v-bind="dotAttrs(dot)"
      />
    </g>

    <!-- notify 蓝点（嵌在轮廓缺口里） -->
    <circle v-if="frame.notif" :cx="frame.notif.x" :cy="frame.notif.y" :r="frame.notif.r" :fill="NOTIF_BLUE" />

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
