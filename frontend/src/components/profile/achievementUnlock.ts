import {
  ACHIEVEMENT_CATALOG,
  type AchievementDef,
  type UnlockRule
} from './achievementCatalog'

export type UnlockProgress = Record<string, number>

export type UnlockContext = {
  documentCount: number
  chatSessionCount: number
  noteCount: number
  streakDays: number
  quizAnswered: number
  quizPerfect: boolean
  quizAccuracy: number
  quizQuestionCount: number
  maxCourseDocCount: number
  progress: UnlockProgress
}

const UNLOCKED_KEY = 'study_copilot_achievements_unlocked'
const PROGRESS_KEY = 'study_copilot_achievement_progress'
const ACTIVE_DAYS_KEY = 'study_copilot_active_days'

export function loadUnlockedIds(): string[] {
  try {
    const raw = localStorage.getItem(UNLOCKED_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.filter((x) => typeof x === 'string') : []
  } catch {
    return []
  }
}

export function saveUnlockedIds(ids: string[]): void {
  try {
    localStorage.setItem(UNLOCKED_KEY, JSON.stringify(ids))
  } catch {
    /* ignore */
  }
}

export function loadProgress(): UnlockProgress {
  try {
    const raw = localStorage.getItem(PROGRESS_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === 'object' ? (parsed as UnlockProgress) : {}
  } catch {
    return {}
  }
}

export function bumpProgress(key: string, delta = 1): UnlockProgress {
  const p = loadProgress()
  const next = Math.max(0, Number(p[key] || 0) + delta)
  p[key] = next
  try {
    localStorage.setItem(PROGRESS_KEY, JSON.stringify(p))
  } catch {
    /* ignore */
  }
  return p
}

export function setProgress(key: string, value: number): UnlockProgress {
  const p = loadProgress()
  p[key] = value
  try {
    localStorage.setItem(PROGRESS_KEY, JSON.stringify(p))
  } catch {
    /* ignore */
  }
  return p
}

/** 记录今日活跃，用于 streak 规则 */
export function markActiveToday(now = new Date()): number {
  const today = now.toISOString().slice(0, 10)
  let days: string[] = []
  try {
    const raw = localStorage.getItem(ACTIVE_DAYS_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) days = parsed.filter((x) => typeof x === 'string')
    }
  } catch {
    days = []
  }
  if (!days.includes(today)) {
    days = [...days, today].sort().slice(-40)
    try {
      localStorage.setItem(ACTIVE_DAYS_KEY, JSON.stringify(days))
    } catch {
      /* ignore */
    }
  }
  return computeStreakDays(days)
}

export function loadActiveDays(): string[] {
  try {
    const raw = localStorage.getItem(ACTIVE_DAYS_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.filter((x) => typeof x === 'string') : []
  } catch {
    return []
  }
}

export function computeStreakDays(days: string[], now = new Date()): number {
  if (!days.length) return 0
  const set = new Set(days)
  const cursor = new Date(now)
  // 允许「今天还没学」也算从昨天起连续
  const today = cursor.toISOString().slice(0, 10)
  if (!set.has(today)) {
    cursor.setUTCDate(cursor.getUTCDate() - 1)
  }
  let streak = 0
  for (;;) {
    const key = cursor.toISOString().slice(0, 10)
    if (!set.has(key)) break
    streak += 1
    cursor.setUTCDate(cursor.getUTCDate() - 1)
    if (streak > 365) break
  }
  return streak
}

export function meetsRule(rule: UnlockRule, ctx: UnlockContext): boolean {
  switch (rule.type) {
    case 'document_count':
      return ctx.documentCount >= rule.gte
    case 'chat_count':
      return ctx.chatSessionCount >= rule.gte
    case 'note_count':
      return ctx.noteCount >= rule.gte
    case 'streak_days':
      return ctx.streakDays >= rule.gte
    case 'quiz_answered':
      return ctx.quizAnswered >= rule.gte
    case 'quiz_perfect':
      return ctx.quizPerfect
    case 'quiz_accuracy':
      return (
        ctx.quizQuestionCount >= rule.minQuestions &&
        ctx.quizAccuracy >= rule.gte
      )
    case 'course_with_docs':
      return ctx.maxCourseDocCount >= rule.minDocs
    case 'progress':
      return Number(ctx.progress[rule.key] || 0) >= rule.gte
    default:
      return false
  }
}

/** 返回本次新解锁的成就 id */
export function evaluateUnlocks(ctx: UnlockContext, unlocked: string[]): string[] {
  const next: string[] = []
  const seen = new Set(unlocked)
  for (const a of ACHIEVEMENT_CATALOG) {
    if (seen.has(a.id)) continue
    if (meetsRule(a.rule, ctx)) next.push(a.id)
  }
  return next
}

/** 仅返回用户已解锁的成就——未解锁内容绝不暴露 */
export function visibleAchievements(unlocked: string[]): AchievementDef[] {
  const set = new Set(unlocked)
  return ACHIEVEMENT_CATALOG.filter((a) => set.has(a.id))
}

export function buildDefaultContext(partial: Partial<UnlockContext> = {}): UnlockContext {
  return {
    documentCount: 0,
    chatSessionCount: 0,
    noteCount: 0,
    streakDays: computeStreakDays(loadActiveDays()),
    quizAnswered: 0,
    quizPerfect: false,
    quizAccuracy: 0,
    quizQuestionCount: 0,
    maxCourseDocCount: 0,
    progress: loadProgress(),
    ...partial
  }
}
