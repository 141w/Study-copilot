import { describe, it, expect } from 'vitest'
import { validatePassword } from '../../src/utils/passwordPolicy'

describe('passwordPolicy', () => {
  it('accepts letter+digit password of length >= 8', () => {
    expect(validatePassword('StudyPass9')).toBeNull()
  })

  it('rejects too short', () => {
    expect(validatePassword('Ab1')).toMatch(/至少/)
  })

  it('rejects letter-only', () => {
    expect(validatePassword('abcdefgh')).toMatch(/数字/)
  })

  it('rejects digit-only', () => {
    expect(validatePassword('12345678')).toMatch(/字母/)
  })

  it('rejects common weak password', () => {
    expect(validatePassword('password123')).toMatch(/常见/)
  })
})
