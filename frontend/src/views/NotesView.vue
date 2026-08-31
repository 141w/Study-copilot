<template>
  <div ref="pageContainer" class="max-w-6xl mx-auto px-6 py-8">
    <!-- Header -->
    <div class="flex items-center justify-between mb-8">
      <div>
        <h1 ref="pageTitle" class="text-2xl font-semibold text-[var(--text-primary)]">笔记</h1>
        <p ref="pageSubtitle" class="text-sm text-[var(--text-muted)] mt-1">记录和管理你的学习笔记</p>
      </div>
      <button @click="openCreateNote" class="btn-primary flex items-center gap-2">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
        新建笔记
      </button>
    </div>

    <!-- Filters -->
    <div class="flex items-center gap-4 mb-6 flex-wrap">
      <input
        v-model="searchInput"
        type="text"
        placeholder="搜索笔记..."
        class="input max-w-xs"
        @input="onSearchInput"
      />

      <select
        v-model="selectedCourseId"
        @change="onCourseFilter"
        class="input max-w-[200px]"
      >
        <option value="">全部课程</option>
        <option v-for="c in courses" :key="c.id" :value="c.id">{{ c.name }}</option>
      </select>

      <div class="flex items-center gap-2 flex-wrap">
        <button
          @click="clearTagFilter"
          class="text-xs px-3 py-1.5 rounded-full transition-colors"
          :class="!selectedTag ? 'bg-[var(--color-primary)] text-white' : 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]'"
        >
          全部标签
        </button>
        <button
          v-for="tag in noteStore.allTags"
          :key="tag"
          @click="selectTag(tag)"
          class="text-xs px-3 py-1.5 rounded-full transition-colors"
          :class="selectedTag === tag ? 'bg-[var(--color-primary)] text-white' : 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]'"
        >
          {{ tag }}
        </button>
      </div>

      <button
        v-if="hasActiveFilters"
        @click="clearAllFilters"
        class="text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors ml-auto"
      >
        清除筛选
      </button>
    </div>

    <!-- Create Note -->
    <div v-if="showCreateEditor" class="mb-6">
      <NoteEditor
        v-model:title="newNoteTitle"
        v-model:content="newNoteContent"
        v-model:tags="newNoteTags"
        @save="debouncedSaveNewNote"
      />
      <div class="flex items-center justify-between mt-3">
        <select v-model="newNoteCourseId" class="input max-w-[200px] text-sm">
          <option value="">不关联课程</option>
          <option v-for="c in courses" :key="c.id" :value="c.id">{{ c.name }}</option>
        </select>
        <div class="flex items-center gap-3">
          <button @click="cancelCreate" class="btn-secondary text-sm">取消</button>
          <button @click="saveNewNote" class="btn-primary text-sm">保存笔记</button>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="noteStore.loading" class="text-center py-16 text-[var(--text-muted)]">加载中...</div>

    <!-- Empty State -->
    <div v-else-if="noteStore.filteredNotes.length === 0" class="text-center py-16">
      <div class="w-20 h-20 mx-auto mb-4 bg-[var(--bg-tertiary)] rounded-full flex items-center justify-center">
        <svg class="w-10 h-10 text-[var(--text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
        </svg>
      </div>
      <p class="text-[var(--text-muted)] mb-2" v-if="hasActiveFilters">未找到匹配的笔记</p>
      <p class="text-[var(--text-muted)] mb-4" v-else>还没有笔记，开始记录吧</p>
      <button @click="openCreateNote" class="btn-secondary text-sm">新建笔记</button>
    </div>

    <!-- Notes Grid -->
    <div v-else ref="notesGrid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <!-- Inline edit -->
      <template v-for="note in noteStore.filteredNotes" :key="note.id">
        <div v-if="editingNoteId === note.id" class="md:col-span-2 lg:col-span-3">
          <NoteEditor
            v-model:title="editNoteTitle"
            v-model:content="editNoteContent"
            v-model:tags="editNoteTags"
            @save="debouncedSaveEditNote"
          />
          <div class="flex items-center justify-between mt-3">
            <select v-model="editNoteCourseId" class="input max-w-[200px] text-sm">
              <option value="">不关联课程</option>
              <option v-for="c in courses" :key="c.id" :value="c.id">{{ c.name }}</option>
            </select>
            <div class="flex items-center gap-3">
              <button @click="cancelEdit" class="btn-secondary text-sm">取消</button>
              <button @click="saveEditNote" class="btn-primary text-sm">保存</button>
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

    <!-- Delete Confirmation -->
    <el-dialog
      v-model="showDeleteConfirm"
      title="删除笔记"
      width="400px"
      :close-on-click-modal="false"
    >
      <p class="text-sm text-[var(--text-secondary)] mb-6">确定要删除「{{ deletingNote?.title || '未命名笔记' }}」吗？此操作不可撤销。</p>
      <template #footer>
        <el-button @click="showDeleteConfirm = false">取消</el-button>
        <el-button type="danger" @click="doDeleteNote">删除</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useNoteStore } from '../stores/note'
import { useCourseStore } from '../stores/course'
import { useToastStore } from '../stores/toast'
import NoteCard from '../components/NoteCard.vue'
import NoteEditor from '../components/NoteEditor.vue'
import gsap from 'gsap'

const noteStore = useNoteStore()
const courseStore = useCourseStore()
const toast = useToastStore()

const pageContainer = ref(null)
const pageTitle = ref(null)
const pageSubtitle = ref(null)
const notesGrid = ref(null)

// Filters
const searchInput = ref('')
const selectedCourseId = ref('')
const selectedTag = ref(null)

// Create note
const showCreateEditor = ref(false)
const newNoteTitle = ref('')
const newNoteContent = ref('')
const newNoteTags = ref([])
const newNoteCourseId = ref('')

// Edit note
const editingNoteId = ref(null)
const editNoteTitle = ref('')
const editNoteContent = ref('')
const editNoteTags = ref([])
const editNoteCourseId = ref('')

// Delete note
const showDeleteConfirm = ref(false)
const deletingNote = ref(null)

let ctx
let searchDebounce = null
let saveDebounceTimer = null

const courses = computed(() => courseStore.courses)
const hasActiveFilters = computed(() =>
  searchInput.value.trim() || selectedCourseId.value || selectedTag.value
)

function courseNameFor(note) {
  if (!note.course_space_id) return ''
  const c = courses.value.find(c => c.id === note.course_space_id)
  return c ? c.name : ''
}

function onSearchInput() {
  clearTimeout(searchDebounce)
  searchDebounce = setTimeout(() => {
    noteStore.setSearchQuery(searchInput.value)
  }, 300)
}

function onCourseFilter() {
  noteStore.setFilterCourse(selectedCourseId.value || null)
}

function selectTag(tag) {
  selectedTag.value = selectedTag.value === tag ? null : tag
  noteStore.setFilterTag(selectedTag.value)
}

function clearTagFilter() {
  selectedTag.value = null
  noteStore.setFilterTag(null)
}

function clearAllFilters() {
  searchInput.value = ''
  selectedCourseId.value = ''
  selectedTag.value = null
  noteStore.clearFilters()
}

// Create
function openCreateNote() {
  showCreateEditor.value = true
  newNoteTitle.value = ''
  newNoteContent.value = ''
  newNoteTags.value = []
  newNoteCourseId.value = ''
}

function cancelCreate() {
  showCreateEditor.value = false
  localStorage.removeItem('note_draft_notes_page')
}

async function saveNewNote() {
  if (!newNoteTitle.value.trim() && !newNoteContent.value.trim()) return
  try {
    await noteStore.createNote({
      title: newNoteTitle.value,
      content: newNoteContent.value,
      tags: newNoteTags.value,
      course_id: newNoteCourseId.value || null
    })
    toast.success('笔记已保存')
    showCreateEditor.value = false
    localStorage.removeItem('note_draft_notes_page')
  } catch (e) {
    toast.error('保存失败')
  }
}

function debouncedSaveNewNote() {
  clearTimeout(saveDebounceTimer)
  saveDebounceTimer = setTimeout(() => {
    localStorage.setItem('note_draft_notes_page', JSON.stringify({
      title: newNoteTitle.value,
      content: newNoteContent.value,
      tags: newNoteTags.value,
      course_id: newNoteCourseId.value
    }))
  }, 1000)
}

// Edit
function openEditNote(note) {
  editingNoteId.value = note.id
  editNoteTitle.value = note.title || ''
  editNoteContent.value = note.content || ''
  editNoteTags.value = [...(note.tags || [])]
  editNoteCourseId.value = note.course_space_id || ''
}

function cancelEdit() {
  editingNoteId.value = null
}

async function saveEditNote() {
  if (!editingNoteId.value) return
  try {
    await noteStore.updateNote(editingNoteId.value, {
      title: editNoteTitle.value,
      content: editNoteContent.value,
      tags: editNoteTags.value,
      course_id: editNoteCourseId.value || null
    })
    toast.success('笔记已更新')
    editingNoteId.value = null
  } catch (e) {
    toast.error('更新失败')
  }
}

function debouncedSaveEditNote() {
  clearTimeout(saveDebounceTimer)
  saveDebounceTimer = setTimeout(() => {
    localStorage.setItem(`note_edit_draft_${editingNoteId.value}`, JSON.stringify({
      title: editNoteTitle.value,
      content: editNoteContent.value,
      tags: editNoteTags.value
    }))
  }, 1000)
}

// Delete
function confirmDeleteNote(note) {
  deletingNote.value = note
  showDeleteConfirm.value = true
}

async function doDeleteNote() {
  if (!deletingNote.value) return
  try {
    await noteStore.deleteNote(deletingNote.value.id)
    toast.success('笔记已删除')
  } catch (e) {
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

  // Restore draft
  const draft = localStorage.getItem('note_draft_notes_page')
  if (draft) {
    try {
      const parsed = JSON.parse(draft)
      if (parsed.title || parsed.content) {
        newNoteTitle.value = parsed.title || ''
        newNoteContent.value = parsed.content || ''
        newNoteTags.value = parsed.tags || []
        newNoteCourseId.value = parsed.course_id || ''
        showCreateEditor.value = true
      }
    } catch (e) { /* ignore */ }
  }

  ctx = gsap.context(() => {
    gsap.from(pageTitle.value, {
      y: 30,
      opacity: 0,
      duration: 0.6,
      ease: 'power2.out'
    })
    gsap.from(pageSubtitle.value, {
      y: 20,
      opacity: 0,
      duration: 0.6,
      delay: 0.1,
      ease: 'power2.out'
    })
  }, pageContainer.value)
})

onUnmounted(() => {
  ctx?.revert()
  clearTimeout(searchDebounce)
  clearTimeout(saveDebounceTimer)
})
</script>
