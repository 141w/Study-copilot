export interface CourseSection {
  id?: string
  title: string
  objective?: string
  difficulty?: string
  key_points?: string[]
}

export interface CourseOutline {
  title?: string
  description?: string
  difficulty?: string
  sections?: CourseSection[]
  cover_image?: string
  image_url?: string
}

export interface ParsedCourseInfo {
  displayText: string
  outline?: CourseOutline
  classroomUrl?: string
  classroomId?: string
  isAiGenerated: boolean
  isPending: boolean
  coverImage?: string
}

/**
 * 防御性解析课程的 description 字段。
 *
 * 后端可能将课程大纲、微课跳转链接等元数据以 JSON 序列化形式存入 description。
 * 本函数提取人类可读文字摘要，并提取大纲与互动微课元数据，彻底杜绝 raw JSON 与转义乱码展示。
 */
export function parseCourseDescription(raw?: string | null): ParsedCourseInfo {
  if (!raw) {
    return {
      displayText: '',
      isAiGenerated: false,
      isPending: false,
    }
  }

  const trimmed = raw.trim()
  if (!trimmed.startsWith('{') && !trimmed.startsWith('[')) {
    return {
      displayText: trimmed,
      isAiGenerated: false,
      isPending: false,
    }
  }

  try {
    const data = JSON.parse(trimmed)
    const outline: CourseOutline | undefined = data.outline
    const classroomUrl = data.classroom_url || ''
    const classroomId = data.classroom_id || data.job_id || ''
    const isPending = !!data.classroom_pending

    let displayText = ''
    if (outline?.description) {
      displayText = outline.description
    } else if (data.description && typeof data.description === 'string') {
      displayText = data.description
    } else if (outline?.title) {
      displayText = outline.title
    } else if (data.requirement) {
      displayText = data.requirement
    } else if (isPending) {
      displayText = 'AI 互动课堂正在后台生成中...'
    } else if (data.event === 'classroom_completed' || classroomUrl) {
      displayText = 'AI 互动微课已就绪，可随时进入沉浸式课堂学习。'
    } else {
      displayText = ''
    }

    const coverImage = outline?.cover_image || outline?.image_url || data.cover_image || ''

    return {
      displayText,
      outline,
      classroomUrl,
      classroomId,
      isAiGenerated: !!(outline || classroomUrl || data.generated || isPending),
      isPending,
      coverImage: coverImage || undefined,
    }
  } catch {
    return {
      displayText: raw,
      isAiGenerated: false,
      isPending: false,
    }
  }
}
