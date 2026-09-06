<template>
  <div ref="pageContainer" class="max-w-6xl mx-auto px-6 py-8">
    <!-- Header（P2-2：PageHeader） -->
    <PageHeader title="笔记" subtitle="记录和管理你的学习笔记">
      <template #actions>
        <el-button @click="openCreateNote" type="primary">
          <el-icon class="mr-1"><Plus /></el-icon>
          新建笔记
        </el-button>
      </template>
    </PageHeader>

    <!-- Filters -->
    <div class="flex items-center gap-4 mb-6 flex-wrap">
      <el-input
        v-model="searchInput"
        :prefix-icon="Search"
        clearable
        placeholder="搜索笔记..."
        class="max-w-xs"
        @input="onSearchInput"
        @clear="onSearchInput"
      />

      <el-select
        v-model="selectedCourseId"
        placeholder="全部课程"
        @change="onCourseFilter"
        class="w-[180px]"
      >
        <el-option value="" label="全部课程" />
        <el-option v-for="c in courses" :key="c.id" :value="c.id" :label="c.name" />
      </el-select>

      <div class="flex items-center gap-2 flex-wrap">
        <el-button
          @click="clearTagFilter"
          size="small"
          round
          :type="!selectedTag ? 'primary' : 'info'"
          :plain="!!selectedTag"
        >
          全部标签 ({{ noteStore.notes.length }})
        </el-button>
        <el-button
          v-for="tag in noteStore.allTags"
          :key="tag"
          @click="selectTag(tag)"
          size="small"
          round
          :type="selectedTag === tag ? 'primary' : 'info'"
          :plain="selectedTag !== tag"
        >
          {{ tag }} <span class="ml-1 text-[11px] opacity-80">({{ tagCountMap[tag] || 0 }})</span>
        </el-button>
      </div>

      <el-button
        v-if="hasActiveFilters"
        @click="clearAllFilters"
        text
        class="text-xs text-[var(--text-muted)]"
      >
        清除筛选
      </el-button>
    </div>

    <!-- Create Note -->
    <div v-if="showCreateEditor" class="mb-6">
      <NoteEditor
        v-model:title="newNote.title"
        v-model:content="newNote.content"
        v-model:tags="newNote.tags"
        @save="onDraftInput('create')"
      />
      <div class="flex items-center justify-between mt-3">
        <el-select v-model="newNote.course_id" placeholder="不关联课程" class="w-[200px]">
          <el-option value="" label="不关联课程" />
          <el-option v-for="c in courses" :key="c.id" :value="c.id" :label="c.name" />
        </el-select>
        <div class="flex items-center gap-3">
          <el-button @click="cancelCreate">取消</el-button>
          <el-button @click="saveNewNote" type="primary">保存笔记</el-button>
        </div>
      </div>
    </div>

    <!-- Loading（P1-2：骨架屏匹配笔记卡片网格形状） -->
    <SkeletonList v-if="noteStore.loading" variant="cards" :count="6" />

    <!-- Empty State（P2-2：EmptyState） -->
    <EmptyState
      v-else-if="noteStore.filteredNotes.length === 0"
      size="lg"
      :icon="EditPen"
      :message="hasActiveFilters ? '未找到匹配的笔记' : '还没有笔记，开始记录吧'"
    >
      <el-button v-if="!hasActiveFilters" @click="openCreateNote">新建笔记</el-button>
    </EmptyState>

    <!-- Notes Grid -->
    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <!-- Inline edit -->
      <template v-for="note in noteStore.filteredNotes" :key="note.id">
        <div v-if="editingNoteId === note.id" class="md:col-span-2 lg:col-span-3">
          <NoteEditor
            v-model:title="editNote.title"
            v-model:content="editNote.content"
            v-model:tags="editNote.tags"
            @save="onDraftInput('edit')"
          />
          <div class="flex items-center justify-between mt-3">
            <el-select v-model="editNote.course_id" placeholder="不关联课程" class="w-[200px]">
              <el-option value="" label="不关联课程" />
              <el-option v-for="c in courses" :key="c.id" :value="c.id" :label="c.name" />
            </el-select>
            <div class="flex items-center gap-3">
              <el-button @click="cancelEdit">取消</el-button>
              <el-button @click="saveEditNote" type="primary">保存</el-button>
            </div>
          </div>
        </div>
        <NoteCard
          v-else
          :note="note"
          :course-name="courseNameFor(note)"
          @click="openEditNote(note)"
          @edit="openEditNote(note)"
          @delete="confirmDeleteNote(note)"
        />
      </template>
    </div>

    <!-- Delete Confirmation（P2-2：ConfirmDialog 替换手写 el-dialog） -->
    <ConfirmDialog
      v-model="showDeleteConfirm"
      title="删除笔记"
      :message="`确定要删除「${deletingNote?.title || '未命名笔记'}」吗？此操作不可撤销。`"
      @confirm="doDeleteNote"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Plus, EditPen, Search } from '@/components/icons'
import { useNoteStore } from '../stores/note'
import type { NoteDetail } from '../stores/note'
import { useCourseStore } from '../stores/course'
import { useToastStore } from '../stores/toast'
import { useNoteDraft, writeNoteDraft, readNoteDraft, removeNoteDraft } from '../composables/useNoteDraft'
import type { NoteDraftData } from '../composables/useNoteDraft'
import NoteCard from '../components/NoteCard.vue'
import NoteEditor from '../components/NoteEditor.vue'
import PageHeader from '../components/common/PageHeader.vue'
import EmptyState from '../components/common/EmptyState.vue'
import ConfirmDialog from '../components/common/ConfirmDialog.vue'
import SkeletonList from '../components/common/SkeletonList.vue'
import { useReducedMotion } from '../composables/useReducedMotion'
import gsap from 'gsap'

interface NoteFormState {
  title: string
  content: string
  tags: string[]
  course_id: string
}

const noteStore = useNoteStore()
const courseStore = useCourseStore()
const toast = useToastStore()
// P1-1：GSAP 动画降级（prefers-reduced-motion）
const { prefersReduced } = useReducedMotion()

const pageContainer = ref<HTMLElement | null>(null)

// P2-4：草稿逻辑由 useNoteDraft 提供（新建场景 key 固定）；
// 编辑场景 key 含笔记 ID（运行期确定），用配套纯函数 + 本地 timer
const newDraft = useNoteDraft('note_draft_notes_page')
let editDraftTimer: ReturnType<typeof setTimeout> | null = null

// Filters
const searchInput = ref('')
const selectedCourseId = ref('')
const selectedTag = ref<string | null>(null)

// Create note
const showCreateEditor = ref(false)
const newNote = ref<NoteFormState>({ title: '', content: '', tags: [], course_id: '' })

// Edit note
const editingNoteId = ref<string | null>(null)
const editNote = ref<NoteFormState>({ title: '', content: '', tags: [], course_id: '' })

// Delete note
const showDeleteConfirm = ref(false)
const deletingNote = ref<NoteDetail | null>(null)

let ctx: gsap.Context | null = null
let searchDebounce: ReturnType<typeof setTimeout> | null = null

const courses = computed(() => courseStore.courses)
const hasActiveFilters = computed(() =>
  searchInput.value.trim() || selectedCourseId.value || selectedTag.value
)

/** 统计每个标签下的笔记数量 */
const tagCountMap = computed<Record<string, number>>(() => {
  const map: Record<string, number> = {}
  noteStore.notes.forEach(note => {
    if (!note.tags) return
    note.tags.forEach(t => {
      const name = typeof t === 'string' ? t : t?.name
      if (name) {
        map[name] = (map[name] || 0) + 1
      }
    })
  })
  return map
})

function courseNameFor(note: NoteDetail): string {
  if (!note.course_space_id) return ''
  const c = courses.value.find(c => c.id === note.course_space_id)
  return c ? c.name : ''
}

function onSearchInput(): void {
  if (searchDebounce) clearTimeout(searchDebounce)
  searchDebounce = setTimeout(() => {
    noteStore.setSearchQuery(searchInput.value)
  }, 300)
}

function onCourseFilter(): void {
  noteStore.setFilterCourse(selectedCourseId.value || null)
}

function selectTag(tag: string): void {
  selectedTag.value = selectedTag.value === tag ? null : tag
  noteStore.setFilterTag(selectedTag.value)
}

function clearTagFilter(): void {
  selectedTag.value = null
  noteStore.setFilterTag(null)
}

function clearAllFilters(): void {
  searchInput.value = ''
  selectedCourseId.value = ''
  selectedTag.value = null
  noteStore.clearFilters()
}

/** 草稿防抖统一入口（NoteEditor @save 触发） */
function onDraftInput(which: 'create' | 'edit'): void {
  if (which === 'create') {
    newDraft.saveDraftDebounced({ ...newNote.value } as NoteDraftData)
  } else if (editingNoteId.value) {
    // 编辑草稿按笔记 ID 分 key（纯函数 + 独立 timer）
    if (editDraftTimer) clearTimeout(editDraftTimer)
    const key = `note_edit_draft_${editingNoteId.value}`
    const data = { ...editNote.value } as NoteDraftData
    editDraftTimer = setTimeout(() => writeNoteDraft(key, data), 1000)
  }
}

// Create
function openCreateNote(): void {
  showCreateEditor.value = true
  newNote.value = { title: '', content: '', tags: [], course_id: '' }
}

function cancelCreate(): void {
  showCreateEditor.value = false
  newDraft.clearDraft()
}

async function saveNewNote(): Promise<void> {
  if (!newNote.value.title.trim() && !newNote.value.content.trim()) return
  try {
    await noteStore.createNote({
      title: newNote.value.title,
      content: newNote.value.content,
      tags: newNote.value.tags,
      course_id: newNote.value.course_id || null
    })
    toast.success('笔记已保存')
    showCreateEditor.value = false
    newDraft.clearDraft()
  } catch (_e) {
    toast.error('保存失败')
  }
}

// Edit
function openEditNote(note: NoteDetail): void {
  editingNoteId.value = note.id
  editNote.value = {
    title: note.title || '',
    content: note.content || '',
    tags: [...(note.tags || [])] as string[],
    course_id: note.course_space_id || ''
  }
  // 恢复该笔记的编辑草稿（如有；P2-4 readNoteDraft 纯函数）
  const restored = readNoteDraft(`note_edit_draft_${note.id}`)
  if (restored && (restored.title || restored.content)) {
    editNote.value.title = restored.title
    editNote.value.content = restored.content
    editNote.value.tags = restored.tags || editNote.value.tags
  }
}

function cancelEdit(): void {
  editingNoteId.value = null
  if (editDraftTimer) {
    clearTimeout(editDraftTimer)
    editDraftTimer = null
  }
}

async function saveEditNote(): Promise<void> {
  if (!editingNoteId.value) return
  try {
    await noteStore.updateNote(editingNoteId.value, {
      title: editNote.value.title,
      content: editNote.value.content,
      tags: editNote.value.tags,
      course_id: editNote.value.course_id || null
    })
    toast.success('笔记已更新')
    // 清除该笔记的编辑草稿
    removeNoteDraft(`note_edit_draft_${editingNoteId.value}`)
    if (editDraftTimer) {
      clearTimeout(editDraftTimer)
      editDraftTimer = null
    }
    editingNoteId.value = null
  } catch (_e) {
    toast.error('更新失败')
  }
}

// Delete
function confirmDeleteNote(note: NoteDetail): void {
  deletingNote.value = note
  showDeleteConfirm.value = true
}

async function doDeleteNote(): Promise<void> {
  if (!deletingNote.value) return
  try {
    await noteStore.deleteNote(deletingNote.value.id)
    toast.success('笔记已删除')
  } catch (_e) {
    toast.error('删除失败')
  }
  showDeleteConfirm.value = false
  deletingNote.value = null
}

onMounted(async () => {
  await Promise.all([
    noteStore.fetchNotes(),
    courseStore.fetchCourses()
  ])

  // 恢复新建草稿（P2-4：useNoteDraft.restoreDraft）
  const draft = newDraft.restoreDraft()
  if (draft) {
    newNote.value = {
      title: draft.title,
      content: draft.content,
      tags: draft.tags || [],
      course_id: draft.course_id || ''
    }
    showCreateEditor.value = true
  }

  // P1-1：减少动态偏好下跳过入场动画
  if (prefersReduced.value) return
  ctx = gsap.context(() => {
    // PageHeader 内的标题/副标题（P2-2 组件化后无模板 ref，按结构选择）
    const header = pageContainer.value?.querySelector('h1')
    const subtitle = pageContainer.value?.querySelector('h1 + p')
    if (header) {
      gsap.from(header, { y: 30, opacity: 0, duration: 0.6, ease: 'power2.out' })
    }
    if (subtitle) {
      gsap.from(subtitle, { y: 20, opacity: 0, duration: 0.6, delay: 0.1, ease: 'power2.out' })
    }
  }, pageContainer.value ?? undefined)
})

onUnmounted(() => {
  ctx?.revert()
  if (searchDebounce) clearTimeout(searchDebounce)
  if (editDraftTimer) clearTimeout(editDraftTimer)
})
</script>
