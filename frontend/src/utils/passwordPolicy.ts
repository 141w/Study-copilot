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
