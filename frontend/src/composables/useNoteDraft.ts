/**
 * useNoteDraft（P2-4）：笔记草稿 + 保存防抖的共享逻辑。
 *
 * 合并 NotesView 与 CourseDetailView 中 ~120 行重复实现：
 *  - localStorage 草稿持久化（防抖写入、恢复、清除）
 *  - 修复原实现共用一个 saveDebounceTimer 导致新建/编辑互相打断的问题
 *    （每处使用点持有独立 timer）
 *
 * 注意：本 composable 必须在 setup 顶层同步调用（内含 onBeforeUnmount）。
 * 运行期才知道 key 的场景（按笔记 ID 存编辑草稿）请用导出的
 * writeNoteDraftDelayed / readNoteDraft / removeNoteDraft 纯函数。
 */
import { ref, onBeforeUnmount } from 'vue'

export interface NoteDraftData {
  title: string
  content: string
  tags: string[]
  course_id?: string
}

/** 纯函数：立即写草稿（空草稿不写） */
export function writeNoteDraft(storageKey: string, d: NoteDraftData): void {
  if (!(d.title.trim() || d.content.trim())) return
  try {
    localStorage.setItem(storageKey, JSON.stringify(d))
  } catch { /* quota 满：忽略草稿失败 */ }
}

/** 纯函数：读草稿；无草稿或解析失败返回 null */
export function readNoteDraft(storageKey: string): NoteDraftData | null {
  try {
    const raw = localStorage.getItem(storageKey)
    if (!raw) return null
    const parsed = JSON.parse(raw) as NoteDraftData
    if (!parsed || (!parsed.title && !parsed.content)) return null
    return {
      title: parsed.title || '',
      content: parsed.content || '',
      tags: parsed.tags || [],
      course_id: parsed.course_id || ''
    }
  } catch {
    return null
  }
}

/** 纯函数：清草稿 */
export function removeNoteDraft(storageKey: string): void {
  localStorage.removeItem(storageKey)
}

/**
 * 草稿延迟写入管理器：key 固定的场景用（如"笔记页新建草稿"）。
 * 在 setup 顶层创建；卸载时自动清理 pending timer 与草稿。
 */
export function useNoteDraft(storageKey: string) {
  let debounceTimer: ReturnType<typeof setTimeout> | null = null
  const draftRestored = ref(false)

  /** 防抖写草稿（默认 1s 静默后落盘） */
  function saveDraftDebounced(data: NoteDraftData, delay = 1000): void {
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => {
      writeNoteDraft(storageKey, data)
    }, delay)
  }

  /** 恢复草稿 */
  function restoreDraft(): NoteDraftData | null {
    const d = readNoteDraft(storageKey)
    if (d) draftRestored.value = true
    return d
  }

  /** 清除草稿（保存成功或取消时调用） */
  function clearDraft(): void {
    if (debounceTimer) {
      clearTimeout(debounceTimer)
      debounceTimer = null
    }
    removeNoteDraft(storageKey)
  }

  onBeforeUnmount(() => {
    if (debounceTimer) clearTimeout(debounceTimer)
  })

  return {
    draftRestored,
    saveDraftDebounced,
    restoreDraft,
    clearDraft
  }
}

