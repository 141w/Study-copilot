import { describe, it, expect, vi, beforeEach } from 'vitest'

// auth store 依赖项（与 tests/stores/auth.test.js 一致的最小 mock）
vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

vi.mock('@/router', () => ({
  default: {
    push: vi.fn(),
  },
}))

import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import { resolveAvatarLetter, useUserAvatar } from '@/composables/useUserAvatar'

describe('resolveAvatarLetter（纯函数）', () => {
  it('英文用户名取首字符并大写', () => {
    expect(resolveAvatarLetter('euler')).toBe('E')
  })

  it('前导空白先 trim 再取首字符', () => {
    expect(resolveAvatarLetter('  grace')).toBe('G')
  })

  it('中文用户名取首字（toUpperCase 不改变汉字）', () => {
    expect(resolveAvatarLetter('王玮琦')).toBe('王')
  })

  it('空串/纯空白/null/undefined 兜底 ?', () => {
    expect(resolveAvatarLetter('')).toBe('?')
    expect(resolveAvatarLetter('   ')).toBe('?')
    expect(resolveAvatarLetter(null)).toBe('?')
    expect(resolveAvatarLetter(undefined)).toBe('?')
  })
})

describe('useUserAvatar', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('未登录时头像字母为 ?', () => {
    const { avatarLetter } = useUserAvatar()
    expect(avatarLetter.value).toBe('?')
  })

  it('跟随 authStore.user 变化重新计算', () => {
    const auth = useAuthStore()
    const { avatarLetter } = useUserAvatar()

    auth.user = { id: 'u1', username: 'euler', email: 'e@example.com' }
    expect(avatarLetter.value).toBe('E')

    auth.user = { id: 'u2', username: ' 王同学', email: 'w@example.com' }
    expect(avatarLetter.value).toBe('王')

    auth.user = null
    expect(avatarLetter.value).toBe('?')
  })
})
