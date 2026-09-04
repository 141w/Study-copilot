/**
 * 指针注视规则（自 bloub/src/ui/gaze.ts 移植，适配 Study Copilot 场景）。
 *
 * bloub 的原版以设置面板为注视目标（TURN 偏移）；这里球悬浮在消息流里，
 * 目标就是指针本身——以球心为原点直接瞄准。角度包络（±16° lacet / ±13° tangage）
 * 与 PITCH 基线是 bloub 选定的值，保留原量：足够与静息漂移（±7°）区分，
 * 又不会让任何眼睛越过球的背面。绝对 PITCH 避免换表情时眼睛高度跳变——这是
 * 原版踩过的坑（neutre 静息 +28.6°，表情在 ±9° 之间，相对混合会猛掉一截）。
 */
import type { Look } from './engine'
import { clamp } from './math'

/** 最大侧向角（度），指针在球右侧一屏外 */
export const YAW_MAX = 16

/** 最大俯仰角（度） */
export const PITCH_MAX = 13

/**
 * 视线基准高度（度，绝对值）：略高于赤道——比"望着虚空"更有"在听"的感觉。
 * 绝对而非相对，理由见文件头。
 */
export const PITCH = 10

export interface Aim {
  /** 指针相对球心的水平偏移，-1..1（右为正），已按半屏归一 */
  nx: number
  /** 垂直偏移，-1..1（下为正，屏幕系） */
  ny: number
  /** 是否有已知指针（false = 触屏/无指针：保留漂移，不凝视死点） */
  pointer: boolean
}

/**
 * 指针 → 注视目标。不做任何表情补偿——混合是引擎的事，只有它知道 t 时刻
 * 正在 morph 的 pose；在这里补偿会读表情的"到达角"而引擎还在过渡中，眼睛必跳。
 *
 * 无指针时 wander: 1 —— 头保持可漂移，球不至于凝视一个死点。
 */
export function lookTarget({ nx, ny, pointer }: Aim): Look {
  return {
    yaw: clamp(nx, -1, 1) * YAW_MAX,
    // 屏幕系 y 向下为正，pitch 向上为正——取反
    pitch: PITCH - clamp(ny, -1, 1) * PITCH_MAX,
    mix: pointer ? 1 : 0,
    spin: 0,
    wander: pointer ? 0 : 1
  }
}
