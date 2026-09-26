/**
 * 部署基址工具的单测。
 *
 * import.meta.env.BASE_URL 在 vitest 下是固定的，因此这里用 vi.stubEnv 覆盖
 * 来验证两种部署形态：独立域名（'/'）与子路径（'/study/'）。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

async function loadBase() {
  vi.resetModules()
  return await import('../../src/services/base')
}

describe('base path helper', () => {
  beforeEach(() => {
    vi.stubEnv('BASE_URL', '/')
  })
  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('根路径部署时不改变任何 URL（与改造前行为一致）', async () => {
    const { withBase, API_BASE } = await loadBase()
    expect(API_BASE).toBe('/api')
    expect(withBase('/api/chat/ask')).toBe('/api/chat/ask')
    expect(withBase('/login')).toBe('/login')
  })

  it('子路径部署时给站内绝对路径加前缀', async () => {
    vi.stubEnv('BASE_URL', '/study/')
    const { withBase, API_BASE } = await loadBase()
    expect(API_BASE).toBe('/study/api')
    expect(withBase('/api/chat/ask')).toBe('/study/api/chat/ask')
    expect(withBase('/classroom-engine/classroom/abc')).toBe('/study/classroom-engine/classroom/abc')
  })

  it('带查询串的模板串也要整体加前缀', async () => {
    vi.stubEnv('BASE_URL', '/study/')
    const { withBase } = await loadBase()
    expect(withBase('/api/chat/stream/7/resume?last_event_id=3')).toBe(
      '/study/api/chat/stream/7/resume?last_event_id=3'
    )
  })

  it('外部绝对 URL 与相对路径原样放行', async () => {
    vi.stubEnv('BASE_URL', '/study/')
    const { withBase } = await loadBase()
    expect(withBase('https://cdn.example.com/a.js')).toBe('https://cdn.example.com/a.js')
    expect(withBase('assets/local.png')).toBe('assets/local.png')
  })
})
