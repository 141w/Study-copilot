/**
 * 与后端 app/core/password_policy.py 对齐的前端校验（提交前提示，后端仍是权威）。
 */

export const PASSWORD_MIN_LENGTH = 8
export const PASSWORD_MAX_LENGTH = 128

const WEAK = new Set([
  'password',
  'password1',
  'password123',
  'passw0rd',
  '12345678',
  '123456789',
  '1234567890',
  '11111111',
  '00000000',
  '88888888',
  '66666666',
  'a1234567',
  'qwerty123',
  'qwertyuiop',
  'qazwsxedc',
  '1qaz2wsx',
  '1q2w3e4r',
  'asdfghjk',
  'zxcvbnm1',
  'admin123',
  'administrator',
  'root1234',
  'letmein123',
  'welcome123',
  'iloveyou1',
  'abc123456',
  'monkey123',
  'dragon123',
  'football',
  'baseball',
  'sunshine',
  'princess'
])

export function validatePassword(password: string): string | null {
  const pwd = password || ''
  if (pwd.length < PASSWORD_MIN_LENGTH) {
    return `密码至少需要 ${PASSWORD_MIN_LENGTH} 位`
  }
  if (pwd.length > PASSWORD_MAX_LENGTH) {
    return `密码最多 ${PASSWORD_MAX_LENGTH} 位`
  }
  if (!/[A-Za-z]/.test(pwd)) {
    return '密码需包含字母'
  }
  if (!/\d/.test(pwd)) {
    return '密码需包含数字'
  }
  if (WEAK.has(pwd.toLowerCase())) {
    return '密码过于常见，请换一个更难猜的密码'
  }
  return null
}

export type PasswordStrength = {
  score: number
  text: string
  barClass: string
  colorClass: string
  tips: string[]
}

/** 注册/改密共用强度评分（0–100）。校验过线 ≠ 强度高。 */
export function passwordStrength(password: string): PasswordStrength {
  const pwd = password || ''
  const tips: string[] = []
  if (!pwd) {
    return {
      score: 0,
      text: '未输入',
      barClass: 'bg-transparent',
      colorClass: 'text-[var(--text-muted)]',
      tips: []
    }
  }

  let score = 0
  if (pwd.length >= 8) score += 25
  else tips.push(`再加 ${8 - pwd.length} 位`)
  if (pwd.length >= 12) score += 15
  if (pwd.length >= 16) score += 10
  if (/[a-z]/.test(pwd)) score += 10
  if (/[A-Z]/.test(pwd)) score += 15
  else tips.push('加入大写字母')
  if (/\d/.test(pwd)) score += 15
  if (/[^A-Za-z0-9]/.test(pwd)) score += 15
  else tips.push('加入符号（如 !@#）')
  if (/(.)\1{2,}/.test(pwd)) {
    score = Math.max(0, score - 15)
    tips.push('避免连续重复字符')
  }

  score = Math.min(100, score)
  if (score < 40) {
    return {
      score,
      text: '弱',
      barClass: 'bg-[var(--color-error)]',
      colorClass: 'text-[var(--color-error)]',
      tips
    }
  }
  if (score < 70) {
    return {
      score,
      text: '中等',
      barClass: 'bg-[var(--color-warning)]',
      colorClass: 'text-[var(--color-warning)]',
      tips
    }
  }
  return {
    score,
    text: '强',
    barClass: 'bg-[var(--color-success)]',
    colorClass: 'text-[var(--color-success)]',
    tips
  }
}
