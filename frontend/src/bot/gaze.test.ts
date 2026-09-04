import { describe, expect, it } from 'vitest'
import { lookTarget, YAW_MAX, PITCH_MAX, PITCH } from './gaze'

describe('lookTarget（指针注视规则）', () => {
  it('指针在右侧 → yaw 为正且封顶 YAW_MAX', () => {
    const look = lookTarget({ nx: 1, ny: 0, pointer: true })
    expect(look.yaw).toBe(YAW_MAX)
    expect(look.mix).toBe(1)
    expect(look.wander).toBe(0)
  })

  it('指针在上方（屏幕 ny 为负）→ pitch 高于基线', () => {
    const look = lookTarget({ nx: 0, ny: -1, pointer: true })
    expect(look.pitch).toBe(PITCH + PITCH_MAX)
  })

  it('指针在下方 → pitch 低于基线但不越过 -PITCH_MAX', () => {
    const look = lookTarget({ nx: 0, ny: 1, pointer: true })
    expect(look.pitch).toBe(PITCH - PITCH_MAX)
  })

  it('超界 nx/ny 被夹紧到 ±1（调用方忘夹时规则自身兜底）', () => {
    const look = lookTarget({ nx: 5, ny: -9, pointer: true })
    expect(look.yaw).toBe(YAW_MAX)
    expect(look.pitch).toBe(PITCH + PITCH_MAX)
  })

  it('无指针 → mix=0（尊重状态表情）且保留漂移 wander=1', () => {
    const look = lookTarget({ nx: 0.5, ny: 0.5, pointer: false })
    expect(look.mix).toBe(0)
    expect(look.wander).toBe(1)
  })
})
