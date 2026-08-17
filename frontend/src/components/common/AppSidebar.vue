<template>
  <!-- Backdrop overlay for mobile sidebar -->
  <Transition name="fade">
    <div
      v-if="sidebarStore.isOpen"
      class="fixed inset-0 bg-black/30 z-30 md:hidden"
      @click="sidebarStore.close()"
    ></div>
  </Transition>

  <aside
    class="fixed left-0 top-16 bottom-0 w-64 bg-[var(--bg-secondary)] border-r border-[var(--border-default)] z-40
           transition-transform duration-300 ease-in-out
           md:translate-x-0"
    :class="sidebarStore.isOpen ? 'translate-x-0' : '-translate-x-full'"
  >
    <nav class="p-4 h-full overflow-y-auto">
      <div class="space-y-1">
        <router-link
          v-for="item in menuItems"
          :key="item.path"
          :to="item.path"
          class="flex items-center gap-3 px-4 py-3 rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition-colors"
          active-class="bg-[var(--surface-card)] shadow-sm text-[var(--text-primary)]"
        >
          <component :is="item.icon" class="w-5 h-5 flex-shrink-0" />
          <span class="text-sm font-medium">{{ item.label }}</span>
        </router-link>
      </div>

      <div class="mt-8">
        <h3 class="px-4 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider mb-2">
          我的文档
        </h3>
        <div class="space-y-1">
          <div
            v-for="doc in documentStore.documents"
            :key="doc.id"
            class="flex items-center gap-2 px-4 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] rounded-lg cursor-pointer"
            :class="{ 'bg-[var(--bg-hover)]': doc.id === selectedDocId }"
            @click="toggleDoc(doc.id)"
          >
            <svg class="w-4 h-4 text-[var(--text-muted)] flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span class="truncate flex-1">{{ doc.filename }}</span>
          </div>
        </div>
      </div>
    </nav>
  </aside>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>

<script setup>
import { ref, onMounted, h } from 'vue'
import { useDocumentStore } from '../../stores/document'
import { useSidebarStore } from '../../stores/sidebar'

const documentStore = useDocumentStore()
const sidebarStore = useSidebarStore()
const selectedDocId = ref(null)

const IconHome = {
  render: () => h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24' }, [
    h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' })
  ])
}

const IconUpload = {
  render: () => h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24' }, [
    h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12' })
  ])
}

const IconChat = {
  render: () => h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24' }, [
    h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z' })
  ])
}

const IconQuiz = {
  render: () => h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24' }, [
    h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4' })
  ])
}

const IconAnalysis = {
  render: () => h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24' }, [
    h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z' })
  ])
}

const IconModelConfig = {
  render: () => h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24' }, [
    h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z' }),
    h('circle', { cx: '12', cy: '12', r: '3' })
  ])
}

const IconDocument = {
  render: () => h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24' }, [
    h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' })
  ])
}

const IconCourse = {
  render: () => h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24' }, [
    h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253' })
  ])
}

const IconNotes = {
  render: () => h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24' }, [
    h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z' })
  ])
}

const menuItems = [
  { path: '/', label: '首页', icon: IconHome },
  { path: '/upload', label: '上传文档', icon: IconUpload },
  { path: '/documents', label: '文档阅读', icon: IconDocument },
  { path: '/courses', label: '课程空间', icon: IconCourse },
  { path: '/notes', label: '笔记', icon: IconNotes },
  { path: '/chat', label: 'AI问答', icon: IconChat },
  { path: '/quiz', label: '做题练习', icon: IconQuiz },
  { path: '/analysis', label: '学习分析', icon: IconAnalysis },
  { path: '/model-config', label: '模型配置', icon: IconModelConfig }
]

function toggleDoc(docId) {
  selectedDocId.value = selectedDocId.value === docId ? null : docId
  documentStore.selectDocument(documentStore.documents.find(d => d.id === docId))
}

onMounted(() => {
  documentStore.fetchDocuments()
})
</script>
