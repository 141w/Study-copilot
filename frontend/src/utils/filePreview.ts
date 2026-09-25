/** File-type sniff + preview classification (Excel/CSV/PDF/Markdown/Image). */

export type PreviewKind = 'pdf' | 'image' | 'text' | 'table' | 'unsupported'

export function detectPreviewKind(
  filename: string,
  mime?: string,
  headBytes?: Uint8Array | string
): PreviewKind {
  const name = (filename || '').toLowerCase()
  const m = (mime || '').toLowerCase()

  if (m.startsWith('image/') || /\.(png|jpe?g|gif|webp|bmp)$/.test(name)) return 'image'
  if (m === 'application/pdf' || name.endsWith('.pdf')) return 'pdf'
  if (/\.(md|markdown|txt|json|log)$/.test(name) || m.startsWith('text/plain')) return 'text'
  if (/\.(csv|tsv)$/.test(name) || m === 'text/csv') return 'table'
  if (/\.(xlsx|xls)$/.test(name) || m.includes('spreadsheet') || m.includes('excel')) return 'table'

  // lightweight sniff: PK zip = xlsx, starts with <html/pdf
  if (headBytes) {
    const head =
      typeof headBytes === 'string'
        ? headBytes.slice(0, 8)
        : String.fromCharCode(...headBytes.slice(0, 8))
    if (head.startsWith('PK')) return 'table'
    if (head.startsWith('%PDF')) return 'pdf'
    if (head.startsWith('\x89PNG')) return 'image'
  }
  return 'unsupported'
}

/** Parse CSV/TSV into rows for table preview (no external dep). */
export function parseDelimited(text: string, delim?: string): string[][] {
  const d = delim || (text.includes('\t') && !text.includes(',') ? '\t' : ',')
  const rows: string[][] = []
  for (const line of text.split(/\r?\n/)) {
    if (!line.trim()) continue
    if (d === '\t') {
      rows.push(line.split('\t'))
    } else {
      // minimal CSV: handle quoted fields
      const out: string[] = []
      let cur = ''
      let q = false
      for (let i = 0; i < line.length; i++) {
        const ch = line[i]
        if (q) {
          if (ch === '"') {
            if (line[i + 1] === '"') {
              cur += '"'
              i++
            } else q = false
          } else cur += ch
        } else if (ch === '"') q = true
        else if (ch === ',') {
          out.push(cur)
          cur = ''
        } else cur += ch
      }
      out.push(cur)
      rows.push(out)
    }
    if (rows.length > 500) break
  }
  return rows
}
