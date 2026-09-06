<template>
  <div ref="pageContainer" class="max-w-6xl mx-auto px-6 py-8">
    <!-- Header（P2-2：PageHeader） -->
    <PageHeader title="课程空间" subtitle="按课程组织你的文档和笔记">
      <template #actions>
        <el-dropdown @command="onCreateAction">
          <el-button type="primary">
            <el-icon class="mr-1"><Plus /></el-icon>
            创建
            <el-icon class="ml-0.5"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="manual">手动创建课程</el-dropdown-item>
              <el-dropdown-item command="generate">AI 生成课程</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </template>
    </PageHeader>

    <!-- Search -->
    <div class="mb-6">
      <el-input
        v-model="searchQuery"
        :prefix-icon="Search"
        clearable
        placeholder="搜索课程..."
        class="max-w-md"
      />
    </div>

    <!-- Loading（批次6：文字加载态 → 骨架屏，匹配三列卡片网格布局） -->
    <SkeletonList v-if="loading" variant="cards" :count="6" />

    <!-- Empty State（P2-2：EmptyState） -->
    <EmptyState
      v-else-if="filteredCourses.length === 0"
      size="lg"
      :icon="Reading"
      :message="searchQuery ? '未找到匹配的课程' : '还没有课程，创建你的第一个课程吧'"
    >
      <el-button @click="openCreateModal">新建课程</el-button>
    </EmptyState>

    <!-- AI 课程生成弹窗 -->
    <el-dialog
      v-model="showGenDialog"
      title="AI 生成课程"
      width="480px"
      :close-on-click-modal="false"
    >
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-[var(--text-secondary)] mb-1.5">课程主题/要求</label>
          <el-input
            v-model="genRequirement"
            type="textarea"
            :rows="2"
            placeholder="e.g. 线性代数第一章：向量空间基础"
            maxlength="500"
            show-word-limit
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-[var(--text-secondary)] mb-1.5">选择参考文档（最多 5 篇）</label>
          <div class="border border-[var(--border-default)] rounded-lg p-2 max-h-40 overflow-y-auto">
            <label
              v-for="doc in readyDocs"
              :key="doc.id"
              class="flex items-center gap-2 px-3 py-2 rounded-md cursor-pointer transition-colors text-sm"
              :class="genDocIds.includes(doc.id)
                ? 'bg-[var(--color-primary)] text-[var(--text-inverse)]'
                : 'bg-[var(--surface-card)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]'"
            >
              <input
                type="checkbox"
                :value="doc.id"
                :checked="genDocIds.includes(doc.id)"
                class="hidden"
                @change="toggleGenDoc(doc.id)"
              />
              <span class="truncate">{{ doc.filename }}</span>
            </label>
            <p v-if="readyDocs.length === 0" class="text-sm text-[var(--text-muted)] text-center py-3">暂无文档</p>
          </div>
        </div>
        <div v-if="genLoading" class="text-sm text-[var(--color-primary)]">正在生成课程，请稍候…</div>
        <div v-if="genError" class="p-3 rounded-lg text-sm bg-[var(--color-error-light)] text-[var(--color-error)]">{{ genError }}</div>
      </div>
      <template #footer>
        <el-button @click="showGenDialog = false">取消</el-button>
        <el-button
          type="primary"
          :disabled="!genRequirement.trim() || genDocIds.length === 0 || genLoading"
          :loading="genLoading"
          @click="generateCourse"
        >
          {{ genLoading ? '生成中…' : '生成课程' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- Course Grid -->
    <div v-if="filteredCourses.length > 0" ref="courseGrid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <CourseCard
        v-for="course in filteredCourses"
        :key="course.id"
        :course="course"
        @click="goToCourse"
        @edit="openEditModal"
        @delete="confirmDelete"
      />
    </div>

    <!-- Create/Edit Modal -->
    <el-dialog
      v-model="showModal"
      :title="editingCourse ? '编辑课程' : '新建课程'"
      width="500px"
      :close-on-click-modal="false"
      @open="animateModalIn"
    >
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-[var(--text-secondary)] mb-1">课程名称</label>
          <el-input
            v-model="form.name"
            placeholder="输入课程名称"
            @keydown.enter="saveCourse"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-[var(--text-secondary)] mb-1">课程描述</label>
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            placeholder="简单描述这门课程（可选）"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-[var(--text-secondary)] mb-2">课程颜色</label>
          <div class="flex items-center gap-2">
            <el-button
              v-for="color in colorOptions"
              :key="color"
              @click="form.color = color"
              class="w-8 h-8 rounded-full border-2 transition-all"
              :class="form.color === color ? 'border-[var(--color-primary)] scale-110' : 'border-transparent'"
              :style="{ backgroundColor: color }"
            ></el-button>
          </div>
        </div>
      </div>

      <template #footer>
        <el-button @click="closeModal">取消</el-button>
        <el-button type="primary" :disabled="!form.name.trim() || saving" @click="saveCourse">
          {{ saving ? '保存中...' : '保存' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- Delete Confirmation（P2-2：ConfirmDialog） -->
    <ConfirmDialog
      v-model="showDeleteConfirm"
      title="删除课程"
      :message="`确定要删除「${deletingCourse?.name}」吗？课程内的文档不会被删除。`"
      @confirm="doDelete"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, Reading, Search } from '@/components/icons'
import { useCourseStore } from '../stores/course'
import { useDocumentStore } from '../stores/document'
import { useToastStore } from '../stores/toast'
import api from '../services/api'
import type { Course } from '../types/models'
import CourseCard from '../components/CourseCard.vue'
import PageHeader from '../components/common/PageHeader.vue'
import EmptyState from '../components/common/EmptyState.vue'
import SkeletonList from '../components/common/SkeletonList.vue'
import ConfirmDialog from '../components/common/ConfirmDialog.vue'
import { useReducedMotion } from '../composables/useReducedMotion'
import gsap from 'gsap'

const router = useRouter()
const courseStore = useCourseStore()
const toast = useToastStore()
// P1-1：GSAP 动画降级（prefers-reduced-motion）
const { prefersReduced } = useReducedMotion()

const pageContainer = ref<HTMLElement | null>(null)
const searchQuery = ref('')
const showModal = ref(false)
const showDeleteConfirm = ref(false)
const editingCourse = ref<Course | null>(null)
const deletingCourse = ref<Course | null>(null)
const saving = ref(false)
const showGenDialog = ref(false)
const genRequirement = ref('')
const genDocIds = ref<string[]>([])
const genLoading = ref(false)
const genError = ref('')

interface CourseForm {
  name: string
  description: string
  color: string
}

const form = ref<CourseForm>({
  name: '',
  description: '',
  // 默认色对齐 DESIGN.md 单色系：ink 纯黑
  color: '#000000'
})

const colorOptions = [
  // 黑白单色系（DESIGN.md）：纯灰阶 8 档，课程区分靠灰度差异。
  // 彩色选项全部移除——品牌即黑白
  '#000000', '#26262b', '#3f3f44', '#5a5a5f',
  '#8a8a92', '#a6a6ad', '#c9c9d4', '#e0e0e8'
]

let ctx: gsap.Context | null = null

const documentStore = useDocumentStore()

const loading = computed(() => courseStore.loading)

const readyDocs = computed(() => documentStore.readyDocuments || [])

const filteredCourses = computed<Course[]>(() => {
  if (!searchQuery.value.trim()) return courseStore.courses
  const q = searchQuery.value.toLowerCase()
  return courseStore.courses.filter(c =>
    c.name.toLowerCase().includes(q) ||
    (c.description && c.description.toLowerCase().includes(q))
  )
})

function openCreateModal(): void {
  editingCourse.value = null
  form.value = { name: '', description: '', color: '#000000' }
  showModal.value = true
}

function onCreateAction(cmd: string): void {
  if (cmd === 'manual') openCreateModal()
  else if (cmd === 'generate') {
    genRequirement.value = ''
    genDocIds.value = []
    genError.value = ''
    showGenDialog.value = true
  }
}

function toggleGenDoc(docId: string): void {
  const idx = genDocIds.value.indexOf(docId)
  if (idx >= 0) genDocIds.value.splice(idx, 1)
  else if (genDocIds.value.length < 5) genDocIds.value.push(docId)
}

async function generateCourse(): Promise<void> {
  genLoading.value = true
  genError.value = ''
  try {
    const { data } = await api.post('/courses/generate', {
      doc_ids: genDocIds.value,
      requirement: genRequirement.value.trim(),
    })
    toast.success(`课程「${data.title}」生成完成！`)
    showGenDialog.value = false
    courseStore.fetchCourses()
    router.push(`/courses/${data.course_id}`)
  }
  catch (e: any) {
    genError.value = e?.response?.data?.detail || e?.message || '生成失败'
  }
  finally {
    genLoading.value = false
  }
}

function openEditModal(course: Course): void {
  editingCourse.value = course
  form.value = {
    name: course.name,
    description: course.description || '',
    color: course.color || '#000000'
  }
  showModal.value = true
}

function closeModal(): void {
  showModal.value = false
  editingCourse.value = null
}

async function saveCourse(): Promise<void> {
  if (!form.value.name.trim()) return
  saving.value = true
  try {
    if (editingCourse.value) {
      await courseStore.updateCourse(editingCourse.value.id, form.value)
      toast.success('课程已更新')
    } else {
      await courseStore.createCourse(form.value)
      toast.success('课程已创建')
    }
    closeModal()
  } catch (_e) {
    toast.error('操作失败，请重试')
  } finally {
    saving.value = false
  }
}

function confirmDelete(course: Course): void {
  deletingCourse.value = course
  showDeleteConfirm.value = true
}

async function doDelete(): Promise<void> {
  if (!deletingCourse.value) return
  try {
    await courseStore.deleteCourse(deletingCourse.value.id)
    toast.success('课程已删除')
  } catch (_e) {
    toast.error('删除失败')
  }
  showDeleteConfirm.value = false
  deletingCourse.value = null
}

function goToCourse(course: Course): void {
  router.push(`/courses/${course.id}`)
}

/** P4-1：modal 入场微上浮（替代旧死代码；reduced-motion 守卫 §6.B）。
 *  @open 时 el-dialog 已挂载于 body，取最上层实例做一次 gsap.from。 */
function animateModalIn(): void {
  if (prefersReduced.value) return
  nextTick(() => {
    const dialog = document.querySelector('.el-overlay-dialog .el-dialog')
    if (dialog) {
      gsap.from(dialog, { y: 16, opacity: 0, duration: 0.25, ease: 'power2.out' })
    }
  })
}

onMounted(() => {
  courseStore.fetchCourses()

  // P1-1：减少动态偏好下跳过入场动画
  if (prefersReduced.value) return
  ctx = gsap.context(() => {
    // P2-2：PageHeader 内化标题后按结构选择（h1 + 其后副标题）
    const header = pageContainer.value?.querySelector('h1')
    const subtitle = header?.nextElementSibling
    if (header) {
      gsap.from(header, {
        y: 30,
        opacity: 0,
        duration: 0.6,
        ease: 'power2.out'
      })
    }
    if (subtitle) {
      gsap.from(subtitle, {
        y: 20,
        opacity: 0,
        duration: 0.6,
        delay: 0.1,
        ease: 'power2.out'
      })
    }
  }, pageContainer.value ?? undefined)
})

onUnmounted(() => {
  ctx?.revert()
})
</script>
