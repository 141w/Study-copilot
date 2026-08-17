<template>
  <div ref="pageContainer" class="max-w-6xl mx-auto px-6 py-8">
    <!-- Back Button -->
    <button
      @click="router.push('/courses')"
      class="flex items-center gap-2 text-gray-500 hover:text-gray-900 transition-colors mb-6"
    >
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
      </svg>
      <span class="text-sm">返回课程列表</span>
    </button>

    <!-- Loading -->
    <div v-if="loading" class="text-center py-16 text-gray-500">加载中...</div>

    <!-- Not Found -->
    <div v-else-if="!course" class="text-center py-16">
      <p class="text-gray-500 mb-4">课程不存在或已被删除</p>
      <router-link to="/courses" class="btn-secondary text-sm">返回课程列表</router-link>
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
              <h1 class="text-2xl font-semibold text-gray-900">{{ course.name }}</h1>
              <p v-if="course.description" class="text-sm text-gray-500 mt-1">{{ course.description }}</p>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <button @click="showNewNote = true" class="btn-secondary flex items-center gap-2 text-sm">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
              新建笔记
            </button>
            <router-link to="/upload" class="btn-primary flex items-center gap-2 text-sm">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
              </svg>
              上传文档
            </router-link>
          </div>
        </div>
      </div>

      <!-- Tabs -->
      <div class="flex items-center gap-6 border-b border-gray-200 mb-6">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          @click="activeTab = tab.key"
          class="pb-3 text-sm font-medium transition-colors relative"
          :class="activeTab === tab.key ? 'text-[#010120]' : 'text-gray-500 hover:text-gray-900'"
        >
          {{ tab.label }}
          <span v-if="tab.count !== undefined" class="ml-1 text-xs text-gray-400">({{ tab.count }})</span>
          <div
            v-if="activeTab === tab.key"
            class="absolute bottom-0 left-0 right-0 h-0.5 bg-[#010120] rounded-full"
          ></div>
        </button>
      </div>

      <!-- Documents Tab removed — backend API not implemented yet -->

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
            <button @click="cancelNewNote" class="btn-secondary text-sm">取消</button>
            <button @click="saveNewNote" class="btn-primary text-sm">保存笔记</button>
          </div>
        </div>

        <div v-if="courseNotes.length === 0 && !showNewNote" class="text-center py-12">
          <div class="w-16 h-16 mx-auto mb-4 bg-gray-100 rounded-full flex items-center justify-center">
            <svg class="w-8 h-8 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
          </div>
          <p class="text-gray-500 mb-4">此课程暂无笔记</p>
          <button @click="showNewNote = true" class="btn-secondary text-sm">创建第一条笔记</button>
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
                <button @click="cancelEditNote" class="btn-secondary text-sm">取消</button>
                <button @click="saveEditNote" class="btn-primary text-sm">保存</button>
              </div>
            </div>
            <NoteCard
              v-else
              :note="note"
              @click="openEditNote(note)"
              @edit="openEditNote(note)"
              @delete="confirmDeleteNote(note)"
            />
          </template>
        </div>
      </div>
    </template>

    <!-- Delete Note Confirmation -->
    <Teleport to="body">
      <div v-if="showDeleteNoteConfirm" class="fixed inset-0 z-50 flex items-center justify-center">
        <div class="absolute inset-0 bg-black/40" @click="showDeleteNoteConfirm = false"></div>
        <div class="relative bg-white rounded-lg shadow-xl w-full max-w-sm mx-4 p-6">
          <h2 class="text-lg font-semibold text-gray-900 mb-2">删除笔记</h2>
          <p class="text-sm text-gray-600 mb-6">确定要删除此笔记吗？此操作不可撤销。</p>
          <div class="flex items-center justify-end gap-3">
            <button @click="showDeleteNoteConfirm = false" class="btn-secondary">取消</button>
            <button @click="doDeleteNote" class="px-4 py-2 bg-red-600 text-white rounded font-medium hover:bg-red-700 transition-colors">删除</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useCourseStore } from '../stores/course'
import { useNoteStore } from '../stores/note'
import { useToastStore } from '../stores/toast'
import NoteCard from '../components/NoteCard.vue'
import NoteEditor from '../components/NoteEditor.vue'
import gsap from 'gsap'

const route = useRoute()
const router = useRouter()
const courseStore = useCourseStore()
const noteStore = useNoteStore()
const toast = useToastStore()

const pageContainer = ref(null)
const courseHeader = ref(null)
const activeTab = ref('documents')
const showNewNote = ref(false)
const editingNoteId = ref(null)

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
  noteStore.notes.filter(n => n.course_id === courseId.value)
)

const tabs = computed(() => [
  { key: 'notes', label: '课程笔记', count: courseNotes.value.length }
])

async function loadCourseData() {
  try {
    await courseStore.fetchCourse(courseId.value)
  } catch (e) {
    toast.error('加载课程数据失败')
  }
}

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
  await noteStore.fetchNotes()

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