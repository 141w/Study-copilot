<template>
  <div ref="pageContainer" class="max-w-6xl mx-auto px-6 py-8">
    <!-- Back Button -->
    <el-button
      @click="router.push('/courses')"
      class="flex items-center gap-2 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors mb-6"
    >
      <el-icon class="w-4 h-4 mr-1"><ArrowLeft /></el-icon>
      <span class="text-sm">返回课程列表</span>
    </el-button>

    <!-- Loading -->
    <!-- Loading（批次6：文字 → 骨架屏；块状变体近似"页头 + tab 列表"的内容量） -->
    <SkeletonList v-if="loading" variant="blocks" :count="2" />

    <!-- Not Found -->
    <EmptyState
      v-else-if="!course"
      size="lg"
      :icon="WarningFilled"
      message="课程不存在或已被删除"
    >
      <router-link to="/courses"><el-button>返回课程列表</el-button></router-link>
    </EmptyState>

    <!-- Course Detail -->
    <template v-else>
      <!-- Course Header -->
      <div ref="courseHeader" class="mb-8">
        <div class="flex items-start justify-between">
          <div class="flex items-center gap-4">
            <div
              class="w-14 h-14 rounded-xl flex items-center justify-center flex-shrink-0"
              :style="{ backgroundColor: (course.color || '#000000') + '20' }"
            >
              <el-icon class="w-7 h-7" :style="{ color: course.color || '#000000' }"><Reading /></el-icon>
            </div>
            <div>
              <h1 class="text-2xl font-semibold text-[var(--text-primary)]">{{ course.name }}</h1>
              <p v-if="course.description" class="text-sm text-[var(--text-muted)] mt-1">{{ course.description }}</p>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <el-button
              type="default"
              class="flex items-center gap-2 text-sm"
              @click="showClassroomBridge = true"
            >
              <el-icon class="w-4 h-4"><VideoPlay /></el-icon>
              生成课堂
            </el-button>
            <el-button v-if="activeTab === 'notes'" @click="showNewNote = true" type="default" class="flex items-center gap-2 text-sm">
              <el-icon class="w-4 h-4"><EditPen /></el-icon>
              新建笔记
            </el-button>
            <router-link to="/upload">
              <el-button type="primary">上传文档</el-button>
            </router-link>
          </div>
        </div>
      </div>

      <!-- Tabs（P2-5：el-tabs 替换手写按钮） -->
      <el-tabs v-model="activeTab" class="mb-6">
        <el-tab-pane :label="`课程文档 (${courseDocuments.length})`" name="documents" />
        <el-tab-pane :label="`课程笔记 (${courseNotes.length})`" name="notes" />
      </el-tabs>

      <!-- Documents Tab -->
      <div v-if="activeTab === 'documents'">
        <div class="flex items-center justify-between mb-4">
          <p class="text-sm text-[var(--text-muted)]">课程关联的文档</p>
          <el-button @click="showAddDocDialog = true">添加文档</el-button>
        </div>

        <EmptyState
          v-if="courseDocuments.length === 0"
          :icon="DocumentAdd"
          message="此课程暂无文档"
        >
          <el-button @click="showAddDocDialog = true">添加第一个文档</el-button>
        </EmptyState>

        <div v-else class="card divide-y divide-[var(--border-default)]">
          <div
            v-for="doc in courseDocuments"
            :key="doc.id"
            class="p-4 flex items-center gap-4"
          >
            <div class="w-10 h-10 bg-[var(--bg-tertiary)] rounded-lg flex items-center justify-center flex-shrink-0">
              <el-icon class="w-5 h-5 text-[var(--text-secondary)]"><Document /></el-icon>
            </div>
            <div class="flex-1 min-w-0">
              <h3 class="font-medium text-[var(--text-primary)] truncate">{{ doc.filename }}</h3>
              <p class="text-sm text-[var(--text-muted)]">{{ doc.chunk_count }} chunks · {{ statusText(doc.status) }}</p>
            </div>
            <el-button
              @click="removeDoc(doc.id)"
              class="text-[var(--text-muted)] hover:text-[var(--color-error)] transition-colors"
              title="从课程移除"
              aria-label="从课程移除"
            >
              <el-icon class="w-5 h-5"><Delete /></el-icon>
            </el-button>
          </div>
        </div>
      </div>

      <!-- Notes Tab -->
      <div v-if="activeTab === 'notes'">
        <!-- New Note Editor -->
        <div v-if="showNewNote" class="mb-6">
          <NoteEditor
            v-model:title="newNote.title"
            v-model:content="newNote.content"
            v-model:tags="newNote.tags"
            @save="onNewNoteDraftInput"
          />
          <div class="flex items-center justify-end gap-3 mt-3">
            <el-button @click="cancelNewNote">取消</el-button>
            <el-button @click="saveNewNote" type="primary">保存笔记</el-button>
          </div>
        </div>

        <EmptyState
          v-if="courseNotes.length === 0 && !showNewNote"
          :icon="EditPen"
          message="此课程暂无笔记"
        >
          <el-button @click="showNewNote = true">创建第一条笔记</el-button>
        </EmptyState>

        <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <!-- Inline edit note -->
          <template v-for="note in courseNotes" :key="note.id">
            <div v-if="editingNoteId === note.id" class="md:col-span-2">
              <NoteEditor
                v-model:title="editNote.title"
                v-model:content="editNote.content"
                v-model:tags="editNote.tags"
                @save="onEditNoteDraftInput"
              />
              <div class="flex items-center justify-end gap-3 mt-3">
                <el-button @click="cancelEditNote">取消</el-button>
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

    <!-- Add Document Dialog（P2-3：DocumentPicker radio 模式） -->
    <el-dialog
      v-model="showAddDocDialog"
      title="添加文档到课程"
      width="500px"
      :close-on-click-modal="false"
    >
      <DocumentPicker
        v-model="selectedDocId"
        mode="radio"
        :documents="availableDocs"
        empty-text="没有可添加的文档，请先上传文档"
      />
      <template #footer>
        <el-button @click="showAddDocDialog = false">取消</el-button>
        <el-button type="primary" :disabled="!selectedDocId" @click="addDoc">添加</el-button>
      </template>
    </el-dialog>

    <!-- Delete Note Confirmation（P2-2：ConfirmDialog） -->
    <ConfirmDialog
      v-model="showDeleteNoteConfirm"
      title="删除笔记"
      message="确定要删除此笔记吗？此操作不可撤销。"
      @confirm="doDeleteNote"
    />

    <!-- OpenMAIC 课堂生成桥接 -->
    <ClassroomBridgeDialog
      v-model="showClassroomBridge"
      :documents="courseDocuments"
      @generated="onClassroomGenerated"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useCourseStore } from '../stores/course'
import { useNoteStore } from '../stores/note'
import type { NoteDetail } from '../stores/note'
import { useDocumentStore } from '../stores/document'
import { useToastStore } from '../stores/toast'
import { useNoteDraft, writeNoteDraft, readNoteDraft, removeNoteDraft } from '../composables/useNoteDraft'
import type { NoteDraftData } from '../composables/useNoteDraft'
import type { Document as DocumentModel } from '../types/models'
import NoteCard from '../components/NoteCard.vue'
import NoteEditor from '../components/NoteEditor.vue'
import EmptyState from '../components/common/EmptyState.vue'
import SkeletonList from '../components/common/SkeletonList.vue'
import ConfirmDialog from '../components/common/ConfirmDialog.vue'
import DocumentPicker from '../components/common/DocumentPicker.vue'
import ClassroomBridgeDialog from '../components/integrations/ClassroomBridgeDialog.vue'
import { useReducedMotion } from '../composables/useReducedMotion'
import { Reading, EditPen, Document, Delete, WarningFilled, DocumentAdd, ArrowLeft, VideoPlay } from '@/components/icons'
import gsap from 'gsap'

interface NoteFormState {
  title: string
  content: string
  tags: string[]
}

const route = useRoute()
const router = useRouter()
const courseStore = useCourseStore()
const noteStore = useNoteStore()
const documentStore = useDocumentStore()
const toast = useToastStore()
// P1-1：GSAP 动画降级（prefers-reduced-motion）
const { prefersReduced } = useReducedMotion()

const pageContainer = ref<HTMLElement | null>(null)
const courseHeader = ref<HTMLElement | null>(null)
const activeTab = ref<'documents' | 'notes'>('documents')
const showNewNote = ref(false)
const editingNoteId = ref<string | null>(null)

// Documents tab
const courseDocuments = ref<DocumentModel[]>([])
const showAddDocDialog = ref(false)
const selectedDocId = ref<string | null>(null)
const showClassroomBridge = ref(false)

// New note form
const newNote = ref<NoteFormState>({ title: '', content: '', tags: [] })

// Edit note form
const editNote = ref<NoteFormState>({ title: '', content: '', tags: [] })

// Delete note
const showDeleteNoteConfirm = ref(false)
const deletingNote = ref<NoteDetail | null>(null)

let ctx: gsap.Context | null = null
// P2-4：草稿逻辑。新建草稿 key 含课程 ID（setup 时 route.params 已可读）；
// 编辑草稿 key 含笔记 ID（运行期确定），用纯函数 + 本地 timer
const newDraft = useNoteDraft(`note_draft_${route.params.id as string}`)
let editDraftTimer: ReturnType<typeof setTimeout> | null = null

const courseId = computed(() => route.params.id as string)
const course = computed(() => courseStore.currentCourse)
const loading = computed(() => courseStore.loading)
const courseNotes = computed<NoteDetail[]>(() =>
  noteStore.notes.filter(n => n.course_space_id === courseId.value)
)
const availableDocs = computed<DocumentModel[]>(() => {
  const inCourse = new Set(courseDocuments.value.map(d => d.id))
  return documentStore.documents.filter(d => d.status === 'ready' && !inCourse.has(d.id))
})

async function loadCourseData(): Promise<void> {
  try {
    await courseStore.fetchCourse(courseId.value)
  } catch (_e) {
    toast.error('加载课程数据失败')
  }
}

async function loadCourseDocuments(): Promise<void> {
  try {
    courseDocuments.value = await courseStore.fetchCourseDocuments(courseId.value)
  } catch (_e) {
    courseDocuments.value = []
  }
}

async function addDoc(): Promise<void> {
  if (!selectedDocId.value) return
  try {
    await courseStore.addDocumentToCourse(courseId.value, selectedDocId.value)
    toast.success('文档已添加到课程')
    showAddDocDialog.value = false
    selectedDocId.value = null
    await loadCourseDocuments()
  } catch (_e) {
    toast.error('添加失败')
  }
}

/** 文档状态中文映射（与其他文档列表页 statusText 对齐） */
function statusText(status: string): string {
  switch (status) {
    case 'ready': return '已就绪'
    case 'processing': return '处理中'
    case 'error': return '错误'
    default: return '待处理'
  }
}

async function removeDoc(docId: string): Promise<void> {
  try {
    await courseStore.removeDocumentFromCourse(courseId.value, docId)
    toast.success('文档已从课程移除')
    await loadCourseDocuments()
  } catch (_e) {
    toast.error('移除失败')
  }
}

// Note CRUD（P2-4：草稿由 useNoteDraft 提供）
function onNewNoteDraftInput(): void {
  newDraft.saveDraftDebounced({ ...newNote.value } as NoteDraftData)
}

function onEditNoteDraftInput(): void {
  if (!editingNoteId.value) return
  if (editDraftTimer) clearTimeout(editDraftTimer)
  const key = `note_edit_draft_${editingNoteId.value}`
  const data = { ...editNote.value } as NoteDraftData
  editDraftTimer = setTimeout(() => writeNoteDraft(key, data), 1000)
}

function cancelNewNote(): void {
  showNewNote.value = false
  newNote.value = { title: '', content: '', tags: [] }
  newDraft.clearDraft()
}

async function saveNewNote(): Promise<void> {
  if (!newNote.value.title.trim() && !newNote.value.content.trim()) return
  try {
    await noteStore.createNote({
      title: newNote.value.title,
      content: newNote.value.content,
      tags: newNote.value.tags,
      course_id: courseId.value
    })
    toast.success('笔记已保存')
    cancelNewNote()
  } catch (_e) {
    toast.error('保存失败')
  }
}

function openEditNote(note: NoteDetail): void {
  editingNoteId.value = note.id
  editNote.value = {
    title: note.title || '',
    content: note.content || '',
    tags: [...(note.tags || [])] as string[]
  }
  // 恢复该笔记的编辑草稿（如有）
  const restored = readNoteDraft(`note_edit_draft_${note.id}`)
  if (restored && (restored.title || restored.content)) {
    editNote.value.title = restored.title
    editNote.value.content = restored.content
    editNote.value.tags = restored.tags || editNote.value.tags
  }
}

function cancelEditNote(): void {
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
      tags: editNote.value.tags
    })
    toast.success('笔记已更新')
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

function confirmDeleteNote(note: NoteDetail): void {
  deletingNote.value = note
  showDeleteNoteConfirm.value = true
}

async function doDeleteNote(): Promise<void> {
  if (!deletingNote.value) return
  try {
    await noteStore.deleteNote(deletingNote.value.id)
    toast.success('笔记已删除')
  } catch (_e) {
    toast.error('删除失败')
  }
  showDeleteNoteConfirm.value = false
  deletingNote.value = null
}

// OpenMAIC 联动：课堂生成完成回调
function onClassroomGenerated(result: { jobId: string; courseId?: string }): void {
  toast.success(`课堂生成已提交！Job: ${result.jobId.slice(0, 8)}…`)
  // 刷新课程数据以同步可能的 course 更新
  loadCourseData()
}

onMounted(async () => {
  await loadCourseData()
  await Promise.all([
    noteStore.fetchNotes(),
    documentStore.fetchDocuments(),
    loadCourseDocuments()
  ])

  // 恢复本课程的新建草稿（key 含课程 ID；P2-4）
  const draft = newDraft.restoreDraft()
  if (draft) {
    newNote.value = {
      title: draft.title,
      content: draft.content,
      tags: draft.tags || []
    }
    showNewNote.value = true
  }

  // P1-1：减少动态偏好下跳过入场动画
  if (prefersReduced.value) return
  ctx = gsap.context(() => {
    if (courseHeader.value) {
      gsap.from(courseHeader.value, {
        y: 30,
        opacity: 0,
        duration: 0.6,
        ease: 'power2.out'
      })
    }
  }, pageContainer.value ?? undefined)
})

onUnmounted(() => {
  ctx?.revert()
  if (editDraftTimer) clearTimeout(editDraftTimer)
})
</script>
