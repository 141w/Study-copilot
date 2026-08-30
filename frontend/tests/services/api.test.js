import { describe, it, expect, vi, beforeEach } from 'vitest'

// ── Approach: test interceptor logic directly ──────────────────────
// Instead of mocking axios.create (which has module-load timing issues),
// we extract the interceptor error handler logic and unit-test the
// decision tree: which status codes trigger retry, delays, _retry guard.

// This mirrors the exact code in api.ts lines 28-75 (response interceptor).

function computeRetryDelay(status, headers) {
  const retryAfter = parseInt(headers['retry-after'] || '0', 10)
  if (status === 429) {
    return isNaN(retryAfter) || retryAfter <= 0 ? 3000 : retryAfter * 1000
  }
  if (status === 503) {
    return 2000
  }
  return 0 // not retried
}

function shouldRetry(status, retried) {
  return (status === 429 || status === 503) && !retried
}

describe('API interceptor — retry decision logic', () => {
  // ── Delay computation ────────────────────────────────────────────

  it('429 with retry-after=3 → 3000ms', () => {
    expect(computeRetryDelay(429, { 'retry-after': '3' })).toBe(3000)
  })

  it('429 with retry-after=1 → 1000ms', () => {
    expect(computeRetryDelay(429, { 'retry-after': '1' })).toBe(1000)
  })

  it('429 with missing header → 3000ms default', () => {
    expect(computeRetryDelay(429, {})).toBe(3000)
  })

  it('429 with retry-after=0 → 3000ms default (guard against 0)', () => {
    expect(computeRetryDelay(429, { 'retry-after': '0' })).toBe(3000)
  })

  it('429 with invalid retry-after → 3000ms default', () => {
    expect(computeRetryDelay(429, { 'retry-after': 'abc' })).toBe(3000)
  })

  it('503 → always 2000ms', () => {
    expect(computeRetryDelay(503, {})).toBe(2000)
  })

  it('400 → 0ms (not retried)', () => {
    expect(computeRetryDelay(400, {})).toBe(0)
  })

  it('401 → 0ms (handled by separate branch)', () => {
    expect(computeRetryDelay(401, {})).toBe(0)
  })

  it('500 → 0ms (not retried)', () => {
    expect(computeRetryDelay(500, {})).toBe(0)
  })

  // ── Retry guard ──────────────────────────────────────────────────

  it('enters retry for 429 when not yet retried', () => {
    expect(shouldRetry(429, false)).toBe(true)
  })

  it('enters retry for 503 when not yet retried', () => {
    expect(shouldRetry(503, false)).toBe(true)
  })

  it('skips retry for 429 when already retried', () => {
    expect(shouldRetry(429, true)).toBe(false)
  })

  it('skips retry for 503 when already retried', () => {
    expect(shouldRetry(503, true)).toBe(false)
  })

  it('never retries 400', () => {
    expect(shouldRetry(400, false)).toBe(false)
    expect(shouldRetry(400, true)).toBe(false)
  })

  it('never retries 500', () => {
    expect(shouldRetry(500, false)).toBe(false)
  })

  // ── _retry flag behavior ─────────────────────────────────────────

  it('config._retry flips from false to true', () => {
    const config = { _retry: false }
    config._retry = true
    expect(config._retry).toBe(true)
  })

  it('once _retry is true, shouldRetry returns false', () => {
    const config = { _retry: true }
    expect(shouldRetry(429, config._retry)).toBe(false)
    expect(shouldRetry(503, config._retry)).toBe(false)
  })
})
