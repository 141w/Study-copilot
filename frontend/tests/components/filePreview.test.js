import { describe, it, expect } from 'vitest'
import { detectPreviewKind, parseDelimited } from '@/utils/filePreview'

describe('filePreview', () => {
  it('按扩展名/嗅探分类', () => {
    expect(detectPreviewKind('a.pdf')).toBe('pdf')
    expect(detectPreviewKind('a.png')).toBe('image')
    expect(detectPreviewKind('a.md')).toBe('text')
    expect(detectPreviewKind('a.csv')).toBe('table')
    expect(detectPreviewKind('a.xlsx')).toBe('table')
    expect(detectPreviewKind('a.bin', '', 'PK\x03\x04')).toBe('table')
    expect(detectPreviewKind('a.bin', '', '????????')).toBe('unsupported')
  })

  it('解析 CSV 引号字段', () => {
    const rows = parseDelimited('a,b\n"x,y",2\n')
    expect(rows[0]).toEqual(['a', 'b'])
    expect(rows[1]).toEqual(['x,y', '2'])
  })

  it('TSV 自动识别', () => {
    const rows = parseDelimited('a\tb\nc\td')
    expect(rows).toEqual([
      ['a', 'b'],
      ['c', 'd'],
    ])
  })
})
