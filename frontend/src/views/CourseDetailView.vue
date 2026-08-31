<template>
  <div ref="pageContainer" class="max-w-6xl mx-auto px-6 py-8">
    <!-- Back Button -->
    <el-button
      @click="router.push('/courses')"
      class="flex items-center gap-2 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors mb-6"
    >
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
      </svg>
      <span class="text-sm">返回课程列表</span>
    </el-button>

    <!-- Loading -->
    <div v-if="loading" class="text-center py-16 text-[var(--text-muted)]">加载中...</div>

    <!-- Not Found -->
    <div v-else-if="!course" class="text-center py-16">
      <p class="text-[var(--text-muted)] mb-4">课程不存在或已被删除</p>
      <router-link to="/courses" >返回课程列表</router-link>
    </div>

    <!-- Course Detail -->
    <template v-else>
      <!-- Course Header -->
      <div ref="courseHeader" class="mb-8">
        <div class="flex items-start justify-between">
          <div class="flex items-center gap-4">
            <div
              class="w-14 h-14 rounded-xl flex items-center justify-center flex-shrink-0"
              :style="{ backgroundColor: (course.color || '#8b5cf6') + '20' }"
            >
              <svg class="w-7 h-7" :style="{ color: course.color || '#8b5cf6' }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
            </div>
            <div>
              <h1 class="text-2xl font-semibold text-[var(--text-primary)]">{{ course.name }}</h1>
              <p v-if="course.description" class="text-sm text-[var(--text-muted)] mt-1">{{ course.description }}</p>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <el-button @click="showNewNote = true" type="default" class="flex items-center gap-2 text-sm">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
              新建笔记
            </el-button>
            <router-link to="/upload" type="primary">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
              </svg>
              上传文档
            </router-link>
          </div>
        </div>
      </div>

      <!-- Tabs -->
      <div class="flex items-center gap-6 border-b border-[var(--border-default)] mb-6">
        <el-button
          v-for="tab in tabs"
          :key="tab.key"
          @click="activeTab = tab.key"
          class="pb-3 text-sm font-medium transition-colors relative"
          :class="activeTab === tab.key ? 'text-[var(--color-primary)]' : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'"
        >
          {{ tab.label }}
          <span v-if="tab.count !== undefined" class="ml-1 text-xs text-[var(--text-muted)]">({{ tab.count }})</span>
          <div
            v-if="activeTab === tab.key"
            class="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--color-primary)] rounded-full"
          ></div>
        </el-button>
      </div>

      <!-- Documents Tab -->
      <div v-if="activeTab === 'documents'">
        <div class="flex items-center justify-between mb-4">
          <p class="text-sm text-[var(--text-muted)]">课程关联的文档</p>
          <el-button @click="showAddDocDialog = true" >添加文档</el-button>
        </div>

        <div v-if="courseDocuments.length === 0" class="text-center py-12">
          <div class="w-16 h-16 mx-auto mb-4 bg-[var(--bg-tertiary)] rounded-full flex items-center justify-center">
            <svg class="w-8 h-8 text-[var(--text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <p class="text-[var(--text-muted)] mb-4">此课程暂无文档</p>
          <el-button @click="showAddDocDialog = true" >添加第一个文档</el-button>
        </div>

        <div v-else class="el-card divide-y divide-gray-100">
          <div
            v-for="doc in courseDocuments"
            :key="doc.id"
            class="p-4 flex items-center gap-4"
          >
            <div class="w-10 h-10 bg-[var(--color-error-light)] rounded-lg flex items-center justify-center flex-shrink-0">
              <svg class="w-5 h-5 text-[var(--color-error)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <div class="flex-1 min-w-0">
              <h3 class="font-medium text-[var(--text-primary)] truncate">{{ doc.filename }}</h3>
              <p class="text-sm text-[var(--text-muted)]">{{ doc.chunk_count }} chunks · {{ doc.status }}</p>
            </div>
            <el-button
              @click="removeDoc(doc.id)"
              class="text-[var(--text-muted)] hover:text-red-500 transition-colors"
              title="从课程移除"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </el-button>
          </div>
        </div>
      </div>

      <!-- Notes Tab -->
      <div v-if="activeTab === 'notes'">
        <!-- New Note Editor -->
        <div v-if="showNewNote" class="mb-6">
          <NoteEditor
            v-model:title="newNoteTitle"
            v-model:content="newNoteContent"
            v-model:tags="newNoteTags"
            @save="debouncedSaveNewNote"
          />
          <div class="flex items-center justify-end gap-3 mt-3">
            <el-button @click="cancelNewNote" >取消</el-button>
            <el-button @click="saveNewNote" type="primary">保存笔记</el-button>
          </div>
        </div>

        <div v-if="courseNotes.length === 0 && !showNewNote" class="text-center py-12">
          <div class="w-16 h-16 mx-auto mb-4 bg-[var(--bg-tertiary)] rounded-full flex items-center justify-center">
            <svg class="w-8 h-8 text-[var(--text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
          </div>
          <p class="text-[var(--text-muted)] mb-4">此课程暂无笔记</p>
          <el-button @click="showNewNote = true" >创建第一条笔记</el-button>
        </div>

        <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <!-- Inline edit note -->
          <template v-for="note in courseNotes" :key="note.id">
            <div v-if="editingNoteId === note.id" class="md:col-span-2">
              <NoteEditor
                v-model:title="editNoteTitle"
                v-model:content="editNoteContent"
                v-model:tags="editNoteTags"
                @save="debouncedSaveEditNote"
              />
              <div class="flex items-center justify-end gap-3 mt-3">
                <el-button @click="cancelEditNote" >取消</el-button>
                <el-button @click="saveEditNote" type="primary">保存</el-button>
              </div>
            </div>
            <NoteCard
              v-else
              :note="note"
              :course-name="course?.name"
              @click="openEditNote(note)"
              @edit="openEditNote(note)"
              @delete="confirmDeleteNote(note)"
            />
          </template>
        </div>
      </div>
    </template>

    <!-- Add Document Dialog -->
    <el-dialog
      v-model="showAddDocDialog"
      title="添加文档到课程"
      width="500px"
      :close-on-click-modal="false"
    >
      <div v-if="availableDocs.length === 0" class="text-sm text-[var(--text-muted)] py-4 text-center">
        没有可添加的文档，请先上传文档
      </div>
      <div v-else class="space-y-2 max-h-64 overflow-y-auto">
        <label
          v-for="doc in availableDocs"
          :key="doc.id"
          class="flex items-center gap-3 p-3 rounded-lg border border-[var(--border-default)] cursor-pointer hover:border-[var(--color-primary)] transition-colors"
        >
          <input type="radio" :value="doc.id" v-model="selectedDocId" class="accent-[var(--color-primary)]" />
          <span class="text-sm text-[var(--text-primary)] truncate">{{ doc.filename }}</span>
        </label>
      </div>
      <template #footer>
        <el-button @click="showAddDocDialog = false">取消</el-button>
        <el-button type="primary" :disabled="!selectedDocId" @click="addDoc">添加</el-button>
      </template>
    </el-dialog>

    <!-- Delete Note Confirmation -->
    <el-dialog
      v-model="showDeleteNoteConfirm"
      title="删除笔记"
      width="400px"
      :close-on-click-modal="false"
    >
      <p class="text-sm text-[var(--text-secondary)] mb-6">确定要删除此笔记吗？此操作不可撤销。</p>
      <template #footer>
        <el-button @click="showDeleteNoteConfirm = false">取消</el-button>
        <el-button type="danger" @click="doDeleteNote">删除</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useCourseStore } from '../stores/course'
import { useNoteStore } from '../stores/note'
import { useDocumentStore } from '../stores/document'
import { useToastStore } from '../stores/toast'
import NoteCard from '../components/NoteCard.vue'
import NoteEditor from '../components/NoteEditor.vue'
import gsap from 'gsap'

const route = useRoute()
const router = useRouter()
const courseStore = useCourseStore()
const noteStore = useNoteStore()
const documentStore = useDocumentStore()
const toast = useToastStore()

const pageContainer = ref(null)
const courseHeader = ref(null)
const activeTab = ref('documents')
const showNewNote = ref(false)
const editingNoteId = ref(null)

// Documents tab
const courseDocuments = ref([])
const showAddDocDialog = ref(false)
const selectedDocId = ref(null)

// New note form
const newNoteTitle = ref('')
const newNoteContent = ref('')
const newNoteTags = ref([])

// Edit note form
const editNoteTitle = ref('')
const editNoteContent = ref('')
const editNoteTags = ref([])

// Delete note
const showDeleteNoteConfirm = ref(false)
const deletingNote = ref(null)

let ctx
let saveDebounceTimer = null

const courseId = computed(() => route.params.id)
const course = computed(() => courseStore.currentCourse)
const loading = computed(() => courseStore.loading)
const courseNotes = computed(() =>
  noteStore.notes.filter(n => n.course_space_id === courseId.value)
)
const availableDocs = computed(() => {
  const inCourse = new Set(courseDocuments.value.map(d => d.id))
  return documentStore.documents.filter(d => d.status === 'ready' && !inCourse.has(d.id))
})

const tabs = computed(() => [
  { key: 'documents', label: '课程文档', count: courseDocuments.value.length },
  { key: 'notes', label: '课程笔记', count: courseNotes.value.length }
])

async function loadCourseData() {
  try {
    await courseStore.fetchCourse(courseId.value)
  } catch (e) {
    toast.error('加载课程数据失败')
  }
}

async function loadCourseDocuments() {
  try {
    courseDocuments.value = await courseStore.fetchCourseDocuments(courseId.value)
  } catch (e) {
    courseDocuments.value = []
  }
}

async function addDoc() {
  if (!selectedDocId.value) return
  try {
    await courseStore.addDocumentToCourse(courseId.value, selectedDocId.value)
    toast.success('文档已添加到课程')
    showAddDocDialog.value = false
    selectedDocId.value = null
    await loadCourseDocuments()
  } catch (e) {
    toast.error('添加失败')
  }
}

async function removeDoc(docId) {
  try {
    await courseStore.removeDocumentFromCourse(courseId.value, docId)
    toast.success('文档已从课程移除')
    await loadCourseDocuments()
  } catch (e) {
    toast.error('移除失败')
  }
}

// Note CRUD
function cancelNewNote() {
  showNewNote.value = false
  newNoteTitle.value = ''
  newNoteContent.value = ''
  newNoteTags.value = []
}

async function saveNewNote() {
  if (!newNoteTitle.value.trim() && !newNoteContent.value.trim()) return
  try {
    await noteStore.createNote({
      title: newNoteTitle.value,
      content: newNoteContent.value,
      tags: newNoteTags.value,
      course_id: courseId.value
    })
    toast.success('笔记已保存')
    cancelNewNote()
  } catch (e) {
    toast.error('保存失败')
  }
}

function debouncedSaveNewNote() {
  clearTimeout(saveDebounceTimer)
  saveDebounceTimer = setTimeout(() => {
    if (newNoteTitle.value.trim() || newNoteContent.value.trim()) {
      // Auto-save draft to localStorage
      localStorage.setItem(`note_draft_${courseId.value}`, JSON.stringify({
        title: newNoteTitle.value,
        content: newNoteContent.value,
        tags: newNoteTags.value
      }))
    }
  }, 1000)
}

function openEditNote(note) {
  editingNoteId.value = note.id
  editNoteTitle.value = note.title || ''
  editNoteContent.value = note.content || ''
  editNoteTags.value = [...(note.tags || [])]
}

function cancelEditNote() {
  editingNoteId.value = null
}

async function saveEditNote() {
  if (!editingNoteId.value) return
  try {
    await noteStore.updateNote(editingNoteId.value, {
      title: editNoteTitle.value,
      content: editNoteContent.value,
      tags: editNoteTags.value
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
    // Auto-save to localStorage as draft
    localStorage.setItem(`note_edit_draft_${editingNoteId.value}`, JSON.stringify({
      title: editNoteTitle.value,
      content: editNoteContent.value,
      tags: editNoteTags.value
    }))
  }, 1000)
}

function confirmDeleteNote(note) {
  deletingNote.value = note
  showDeleteNoteConfirm.value = true
}

async function doDeleteNote() {
  if (!deletingNote.value) return
  try {
    await noteStore.deleteNote(deletingNote.value.id)
    toast.success('笔记已删除')
  } catch (e) {
    toast.error('删除失败')
  }
  showDeleteNoteConfirm.value = false
  deletingNote.value = null
}

onMounted(async () => {
  await loadCourseData()
  await Promise.all([
    noteStore.fetchNotes(),
    documentStore.fetchDocuments(),
    loadCourseDocuments()
  ])

  // Restore draft if exists
  const draft = localStorage.getItem(`note_draft_${courseId.value}`)
  if (draft) {
    try {
      const parsed = JSON.parse(draft)
      if (parsed.title || parsed.content) {
        newNoteTitle.value = parsed.title || ''
        newNoteContent.value = parsed.content || ''
        newNoteTags.value = parsed.tags || []
        showNewNote.value = true
      }
    } catch (e) { /* ignore */ }
  }

  ctx = gsap.context(() => {
    if (courseHeader.value) {
      gsap.from(courseHeader.value, {
        y: 30,
        opacity: 0,
        duration: 0.6,
        ease: 'power2.out'
      })
    }
  }, pageContainer.value)
})

onUnmounted(() => {
  ctx?.revert()
  clearTimeout(saveDebounceTimer)
})
</script>
