import { describe, it, expect } from 'vitest'
import {
  formatRelativeTime,
  formatDayLabel,
  formatSize,
  formatTime,
  cleanPdfText
} from '@/composables/useFormat'

describe('useFormat', () => {
  describe('formatRelativeTime', () => {
    it('空值返回空串', () => {
      expect(formatRelativeTime(null)).toBe('')
      expect(formatRelativeTime(undefined)).toBe('')
      expect(formatRelativeTime('')).toBe('')
    })

    it('1 分钟内 → 刚刚', () => {
      expect(formatRelativeTime(new Date(Date.now() - 10_000).toISOString())).toBe('刚刚')
    })

    it('1 小时内 → N 分钟前', () => {
      expect(formatRelativeTime(new Date(Date.now() - 5 * 60_000).toISOString())).toBe('5 分钟前')
    })

    it('24 小时内 → N 小时前', () => {
      expect(formatRelativeTime(new Date(Date.now() - 3 * 3_600_000).toISOString())).toBe('3 小时前')
    })

    it('48 小时内 → 昨天', () => {
      expect(formatRelativeTime(new Date(Date.now() - 30 * 3_600_000).toISOString())).toBe('昨天')
    })

    it('一周内 → N 天前', () => {
      expect(formatRelativeTime(new Date(Date.now() - 4 * 86_400_000).toISOString())).toBe('4 天前')
    })

    it('一周外 → 短日期（月 日）', () => {
      const label = formatRelativeTime(new Date(Date.now() - 30 * 86_400_000).toISOString())
      // 形如 "7月2日"（按本地时区）
      expect(label).toMatch(/\d+月\d+日/)
    })

    it('未来时间 → 短日期（不显示负数）', () => {
      const label = formatRelativeTime(new Date(Date.now() + 86_400_000).toISOString())
      expect(label).toMatch(/\d+月\d+日/)
    })
  })

  describe('formatDayLabel', () => {
    it('今天', () => {
      expect(formatDayLabel(new Date().toISOString())).toBe('今天')
    })
    it('昨天', () => {
      expect(formatDayLabel(new Date(Date.now() - 25 * 3_600_000).toISOString())).toBe('昨天')
    })
    it('一周内 → N天前', () => {
      expect(formatDayLabel(new Date(Date.now() - 3 * 86_400_000).toISOString())).toBe('3天前')
    })
    it('空值', () => {
      expect(formatDayLabel('')).toBe('')
    })
  })

  describe('formatSize', () => {
    it('0 / 空值', () => {
      expect(formatSize(0)).toBe('0 B')
      expect(formatSize(null)).toBe('0 B')
    })
    it('字节', () => {
      expect(formatSize(500)).toBe('500.0 B')
    })
    it('KB', () => {
      expect(formatSize(2048)).toBe('2.0 KB')
    })
    it('MB', () => {
      expect(formatSize(5 * 1024 * 1024)).toBe('5.0 MB')
    })
    it('GB 封顶', () => {
      expect(formatSize(3 * 1024 ** 3)).toBe('3.0 GB')
    })
  })

  describe('formatTime', () => {
    it('空值', () => {
      expect(formatTime(null)).toBe('')
    })
    it('非法输入容错', () => {
      // new Date('garbage') → Invalid Date，toLocaleTimeString 会抛 RangeError
      // 但实现里 catch 了 → 返回空串
      expect(formatTime('not-a-date')).toBe('')
    })
  })

  describe('cleanPdfText', () => {
    it('空值', () => {
      expect(cleanPdfText(null)).toBe('')
      expect(cleanPdfText('')).toBe('')
    })
    it('句间换行保留', () => {
      expect(cleanPdfText('第一句。\n第二句。')).toBe('第一句。\n第二句。')
    })
    it('非句间单换行合并为空格', () => {
      expect(cleanPdfText('中间\n断行')).toBe('中间 断行')
    })
    it('多段保留段落结构', () => {
      const text = '段落一。\n段落二。\n\n'
      expect(cleanPdfText(text)).toBe(text.trim())
    })
  })
})
