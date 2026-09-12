import { describe, it, expect } from 'vitest'

function normalizeOptionLabel(opt) {
  if (typeof opt === 'string') {
    const m = opt.match(/^([A-Da-d])[.、)\s]\s*(.*)$/)
    return { text: m ? m[2] || opt : opt, value: m ? m[1].toUpperCase() : opt }
  }
  const label = String(opt?.label ?? opt?.text ?? '')
  const m = label.match(/^([A-Da-d])[.、)\s]\s*(.*)$/)
  return {
    text: m ? m[2] || label : label,
    value: String(opt?.value || (m ? m[1].toUpperCase() : label)),
  }
}

function normalizeQuiz(raw) {
  if (!raw) return null
  const q = raw.question ? raw : Array.isArray(raw.questions) && raw.questions.length ? raw.questions[0] : null
  if (!q) return null
  const opts = (q.options || []).map(normalizeOptionLabel)
  const answerRaw = q.answer
  const answerVals = Array.isArray(answerRaw)
    ? answerRaw.map(String)
    : answerRaw != null && answerRaw !== ''
      ? [String(answerRaw)]
      : []
  const correctValues = new Set()
  for (const a of answerVals) {
    correctValues.add(a)
    const hit = opts.find(o => o.value === a || o.text === a)
    if (hit) {
      correctValues.add(hit.value)
      correctValues.add(hit.text)
    }
  }
  return {
    question: String(q.question || ''),
    options: opts.map(o => o.text),
    correctValues: [...correctValues],
    explanation: String(q.analysis || q.explanation || ''),
  }
}

describe('classroom quiz normalize', () => {
  it('maps OpenMAIC questions[] schema', () => {
    const n = normalizeQuiz({
      type: 'quiz',
      questions: [
        {
          question: '属于信号学习的是？',
          options: [
            { label: 'A. 听铃声安静', value: 'A' },
            { label: 'B. 背口诀', value: 'B' },
          ],
          answer: ['A'],
          analysis: '铃声是信号',
        },
      ],
    })
    expect(n.question).toContain('信号学习')
    expect(n.options[0]).toBe('听铃声安静')
    expect(n.correctValues).toContain('A')
    expect(n.correctValues).toContain('听铃声安静')
    expect(n.explanation).toContain('铃声')
  })

  it('maps legacy simplified quiz object', () => {
    const n = normalizeQuiz({
      question: '旧题干',
      options: ['选项一', '选项二'],
      answer: '选项一',
      explanation: '解析',
    })
    expect(n.question).toBe('旧题干')
    expect(n.correctValues).toContain('选项一')
  })
})
