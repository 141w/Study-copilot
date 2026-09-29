export type StickerDef = {
  id: string
  label: string
  /** 贴纸图（透明底） */
  img: string
  /** 默认落点：相对舞台的百分比坐标 */
  x: number
  y: number
  rot: number
}

export type StickerLayoutItem = { x: number; y: number; rot: number }

export const ACHIEVEMENT_LAYOUT_KEY = 'study_copilot_achievement_layout'
export const ACHIEVEMENT_PLACED_KEY = 'study_copilot_achievement_placed'

/** 画布默认落点（按序号横向散布，覆盖通栏点阵场） */
export const STICKER_SLOTS: Array<{ x: number; y: number; rot: number }> = [
  { x: 10, y: 22, rot: -8 },
  { x: 24, y: 16, rot: 6 },
  { x: 38, y: 24, rot: -4 },
  { x: 52, y: 14, rot: 10 },
  { x: 66, y: 22, rot: -6 },
  { x: 80, y: 16, rot: 8 },
  { x: 16, y: 52, rot: -10 },
  { x: 34, y: 58, rot: 5 },
  { x: 55, y: 50, rot: -7 },
  { x: 74, y: 56, rot: 4 }
]

export function slotForIndex(index: number): { x: number; y: number; rot: number } {
  return STICKER_SLOTS[index % STICKER_SLOTS.length]
}
