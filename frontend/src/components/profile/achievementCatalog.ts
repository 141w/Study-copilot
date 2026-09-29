import firstDocument from '@/assets/achievements/first-document.png'
import firstAsk from '@/assets/achievements/first-ask.png'
import citedAnswer from '@/assets/achievements/cited-answer.png'
import noteKeeper from '@/assets/achievements/note-keeper.png'
import streak7 from '@/assets/achievements/streak-7.png'
import streak30 from '@/assets/achievements/streak-30.png'
import note50 from '@/assets/achievements/note-50.png'
import quiz50 from '@/assets/achievements/quiz-50.png'
import perfectScore from '@/assets/achievements/perfect-score.png'
import accuracy90 from '@/assets/achievements/accuracy-90.png'
import wrongHunter from '@/assets/achievements/wrong-hunter.png'
import courseBuilder from '@/assets/achievements/course-builder.png'
import roundtable from '@/assets/achievements/roundtable.png'
import microLesson from '@/assets/achievements/micro-lesson.png'
import alchemist from '@/assets/achievements/alchemist.png'
import memoryKeeper from '@/assets/achievements/memory-keeper.png'
import voiceReader from '@/assets/achievements/voice-reader.png'
import knowledgeLibrarian from '@/assets/achievements/knowledge-librarian.png'

export type AchievementTier = 'common' | 'rare' | 'epic'

export type UnlockRule =
  | { type: 'document_count'; gte: number }
  | { type: 'chat_count'; gte: number }
  | { type: 'note_count'; gte: number }
  | { type: 'streak_days'; gte: number }
  | { type: 'quiz_answered'; gte: number }
  | { type: 'quiz_perfect' }
  | { type: 'quiz_accuracy'; gte: number; minQuestions: number }
  | { type: 'course_with_docs'; minDocs: number }
  | { type: 'progress'; key: string; gte: number }

export type AchievementDef = {
  id: string
  name: string
  summary: string
  /** 展示用获取方式文案 */
  unlockRule: string
  /** 程序化触发条件 */
  rule: UnlockRule
  tier: AchievementTier
  image: string
  group: '入门' | '学习' | '练习' | '进阶'
}

export const TIER_LABEL: Record<AchievementTier, string> = {
  common: '普通',
  rare: '稀有',
  epic: '史诗'
}

/**
 * 完整成就目录（含未解锁）。
 * UI 层只允许展示 unlocked，未解锁内容对用户不可见。
 */
export const ACHIEVEMENT_CATALOG: AchievementDef[] = [
  {
    id: 'first-document',
    name: '知识启航',
    summary: '上传并完成第 1 份文档解析',
    unlockRule: '成功上传并解析 1 份文档',
    rule: { type: 'document_count', gte: 1 },
    tier: 'common',
    image: firstDocument,
    group: '入门'
  },
  {
    id: 'first-ask',
    name: '初次问答',
    summary: '向知识库问出第一个问题',
    unlockRule: '完成 1 次 AI 问答',
    rule: { type: 'chat_count', gte: 1 },
    tier: 'common',
    image: firstAsk,
    group: '入门'
  },
  {
    id: 'cited-answer',
    name: '答疑有据',
    summary: '善用带引用的 AI 问答',
    unlockRule: '累计完成 10 次会话问答',
    rule: { type: 'chat_count', gte: 10 },
    tier: 'common',
    image: citedAnswer,
    group: '学习'
  },
  {
    id: 'note-keeper',
    name: '笔耕成章',
    summary: '坚持沉淀学习笔记',
    unlockRule: '累计创建 10 篇笔记',
    rule: { type: 'note_count', gte: 10 },
    tier: 'common',
    image: noteKeeper,
    group: '学习'
  },
  {
    id: 'streak-7',
    name: '持之以恒',
    summary: '连续 7 天点亮学习热力',
    unlockRule: '连续 7 天有学习活动',
    rule: { type: 'streak_days', gte: 7 },
    tier: 'rare',
    image: streak7,
    group: '学习'
  },
  {
    id: 'streak-30',
    name: '水滴石穿',
    summary: '连续 30 天点亮学习热力',
    unlockRule: '连续 30 天有学习活动',
    rule: { type: 'streak_days', gte: 30 },
    tier: 'epic',
    image: streak30,
    group: '学习'
  },
  {
    id: 'note-50',
    name: '著作等身',
    summary: '沉淀 50 篇学习笔记',
    unlockRule: '累计创建 50 篇笔记',
    rule: { type: 'note_count', gte: 50 },
    tier: 'rare',
    image: note50,
    group: '学习'
  },
  {
    id: 'quiz-50',
    name: '沙场点兵',
    summary: '刷题路上稳步前行',
    unlockRule: '累计作答 50 道练习题',
    rule: { type: 'quiz_answered', gte: 50 },
    tier: 'common',
    image: quiz50,
    group: '练习'
  },
  {
    id: 'perfect-score',
    name: '满分时刻',
    summary: '一次测验全部答对',
    unlockRule: '单次测验正确率 100%',
    rule: { type: 'quiz_perfect' },
    tier: 'rare',
    image: perfectScore,
    group: '练习'
  },
  {
    id: 'accuracy-90',
    name: '十拿九稳',
    summary: '高正确率完成一套题',
    unlockRule: '单次测验 ≥10 题且正确率 ≥90%',
    rule: { type: 'quiz_accuracy', gte: 0.9, minQuestions: 10 },
    tier: 'rare',
    image: accuracy90,
    group: '练习'
  },
  {
    id: 'wrong-hunter',
    name: '错题猎人',
    summary: '反复打磨薄弱点',
    unlockRule: '使用错题分析 5 次',
    rule: { type: 'progress', key: 'wrong_review_count', gte: 5 },
    tier: 'common',
    image: wrongHunter,
    group: '练习'
  },
  {
    id: 'course-builder',
    name: '体系构建',
    summary: '搭起自己的课程知识体系',
    unlockRule: '创建课程并关联至少 3 份文档',
    rule: { type: 'course_with_docs', minDocs: 3 },
    tier: 'rare',
    image: courseBuilder,
    group: '进阶'
  },
  {
    id: 'roundtable',
    name: '圆桌学者',
    summary: '发起多角色深度研讨',
    unlockRule: '完成 1 次多角色研讨',
    rule: { type: 'progress', key: 'discussion_count', gte: 1 },
    tier: 'epic',
    image: roundtable,
    group: '进阶'
  },
  {
    id: 'micro-lesson',
    name: '微课制作人',
    summary: '生成 AI 互动微课',
    unlockRule: '成功生成 1 次 AI 课堂/微课',
    rule: { type: 'progress', key: 'classroom_count', gte: 1 },
    tier: 'epic',
    image: microLesson,
    group: '进阶'
  },
  {
    id: 'alchemist',
    name: '炼金术士',
    summary: '玩转内容形态转换',
    unlockRule: '使用至少 5 种不同内容转换',
    rule: { type: 'progress', key: 'transform_variety', gte: 5 },
    tier: 'rare',
    image: alchemist,
    group: '进阶'
  },
  {
    id: 'memory-keeper',
    name: '记忆管家',
    summary: '善用长期记忆',
    unlockRule: '确认 5 条长期记忆',
    rule: { type: 'progress', key: 'memory_confirmed', gte: 5 },
    tier: 'common',
    image: memoryKeeper,
    group: '进阶'
  },
  {
    id: 'voice-reader',
    name: '声入人心',
    summary: '用声音陪伴学习',
    unlockRule: '使用 TTS 朗读 10 次',
    rule: { type: 'progress', key: 'tts_count', gte: 10 },
    tier: 'common',
    image: voiceReader,
    group: '进阶'
  },
  {
    id: 'knowledge-librarian',
    name: '知识馆长',
    summary: '规模化个人知识库',
    unlockRule: '文档总数达到 20 份',
    rule: { type: 'document_count', gte: 20 },
    tier: 'rare',
    image: knowledgeLibrarian,
    group: '进阶'
  }
]

export const ACHIEVEMENT_GROUPS = ['入门', '学习', '练习', '进阶'] as const

export function getAchievement(id: string): AchievementDef | undefined {
  return ACHIEVEMENT_CATALOG.find((a) => a.id === id)
}
