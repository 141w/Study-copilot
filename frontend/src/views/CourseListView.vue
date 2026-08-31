<template>
  <div ref="pageContainer" class="max-w-6xl mx-auto px-6 py-8">
    <!-- Header -->
    <div class="flex items-center justify-between mb-8">
      <div>
        <h1 ref="pageTitle" class="text-2xl font-semibold text-[var(--text-primary)]">课程空间</h1>
        <p ref="pageSubtitle" class="text-sm text-[var(--text-muted)] mt-1">按课程组织你的文档和笔记</p>
      </div>
      <el-button
        @click="openCreateModal"
        type="primary"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
        新建课程
      </el-button>
    </div>

    <!-- Search -->
    <div class="mb-6">
      <input
        v-model="searchQuery"
        type="text"
        placeholder="搜索课程..."
        class="input max-w-md"
      />
    </div>

    <!-- Loading -->
    <div v-if="loading" class="text-center py-16 text-[var(--text-muted)]">
      加载中...
    </div>

    <!-- Empty State -->
    <div v-else-if="filteredCourses.length === 0" class="text-center py-16">
      <div class="w-20 h-20 mx-auto mb-4 bg-[var(--bg-tertiary)] rounded-full flex items-center justify-center">
        <svg class="w-10 h-10 text-[var(--text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
        </svg>
      </div>
      <p class="text-[var(--text-muted)] mb-2" v-if="searchQuery">未找到匹配的课程</p>
      <p class="text-[var(--text-muted)] mb-4" v-else>还没有课程，创建你的第一个课程吧</p>
      <el-button @click="openCreateModal" >新建课程</el-button>
    </div>

    <!-- Course Grid -->
    <div v-else ref="courseGrid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
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

    <!-- Delete Confirmation -->
    <el-dialog
      v-model="showDeleteConfirm"
      title="删除课程"
      width="400px"
      :close-on-click-modal="false"
    >
      <p class="text-sm text-[var(--text-secondary)] mb-6">
        确定要删除「{{ deletingCourse?.name }}」吗？课程内的文档不会被删除。
      </p>
      <template #footer>
        <el-button @click="showDeleteConfirm = false">取消</el-button>
        <el-button type="danger" @click="confirmDelete">删除</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useCourseStore } from '../stores/course'
import { useToastStore } from '../stores/toast'
import CourseCard from '../components/CourseCard.vue'
import gsap from 'gsap'

const router = useRouter()
const courseStore = useCourseStore()
const toast = useToastStore()

const pageContainer = ref(null)
const pageTitle = ref(null)
const pageSubtitle = ref(null)
const courseGrid = ref(null)
const modalEl = ref(null)
const searchQuery = ref('')
const showModal = ref(false)
const showDeleteConfirm = ref(false)
const editingCourse = ref(null)
const deletingCourse = ref(null)
const saving = ref(false)

const form = ref({
  name: '',
  description: '',
  color: '#8b5cf6'
})

const colorOptions = [
  '#ef4444', '#f97316', '#eab308', '#22c55e',
  '#3b82f6', '#8b5cf6', '#ec4899', '#010120'
]

let ctx

const loading = computed(() => courseStore.loading)

const filteredCourses = computed(() => {
  if (!searchQuery.value.trim()) return courseStore.courses
  const q = searchQuery.value.toLowerCase()
  return courseStore.courses.filter(c =>
    c.name.toLowerCase().includes(q) ||
    (c.description && c.description.toLowerCase().includes(q))
  )
})

function openCreateModal() {
  editingCourse.value = null
  form.value = { name: '', description: '', color: '#8b5cf6' }
  showModal.value = true
  nextTick(() => animateModalIn())
}

function openEditModal(course) {
  editingCourse.value = course
  form.value = {
    name: course.name,
    description: course.description || '',
    color: course.color || '#8b5cf6'
  }
  showModal.value = true
  nextTick(() => animateModalIn())
}

function closeModal() {
  showModal.value = false
  editingCourse.value = null
}

async function saveCourse() {
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
  } catch (e) {
    toast.error('操作失败，请重试')
  } finally {
    saving.value = false
  }
}

function confirmDelete(course) {
  deletingCourse.value = course
  showDeleteConfirm.value = true
}

async function doDelete() {
  if (!deletingCourse.value) return
  try {
    await courseStore.deleteCourse(deletingCourse.value.id)
    toast.success('课程已删除')
  } catch (e) {
    toast.error('删除失败')
  }
  showDeleteConfirm.value = false
  deletingCourse.value = null
}

function goToCourse(course) {
  router.push(`/courses/${course.id}`)
}

function animateModalIn() {
  if (modalEl.value) {
    gsap.from(modalEl.value, {
      y: 20,
      opacity: 0,
      duration: 0.25,
      ease: 'power2.out'
    })
  }
}

onMounted(() => {
  courseStore.fetchCourses()

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
})
</script>
