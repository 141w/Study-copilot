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
          <el-icon class="w-5 h-5 flex-shrink-0">
            <component :is="item.icon" />
          </el-icon>
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
            <el-icon class="w-4 h-4 text-[var(--text-muted)] flex-shrink-0">
              <Document />
            </el-icon>
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
import { ref, onMounted } from 'vue'
import { useDocumentStore } from '../../stores/document'
import { useSidebarStore } from '../../stores/sidebar'
import {
  HomeFilled, Upload, Document, Reading, Edit,
  ChatDotSquare, DocumentChecked, TrendCharts, Setting
} from '@element-plus/icons-vue'

const documentStore = useDocumentStore()
const sidebarStore = useSidebarStore()
const selectedDocId = ref(null)

const menuItems = [
  { path: '/', label: '首页', icon: HomeFilled },
  { path: '/upload', label: '上传文档', icon: Upload },
  { path: '/documents', label: '文档阅读', icon: Document },
  { path: '/courses', label: '课程空间', icon: Reading },
  { path: '/notes', label: '笔记', icon: Edit },
  { path: '/chat', label: 'AI问答', icon: ChatDotSquare },
  { path: '/quiz', label: '做题练习', icon: DocumentChecked },
  { path: '/analysis', label: '学习分析', icon: TrendCharts },
  { path: '/model-config', label: '模型配置', icon: Setting }
]

function toggleDoc(docId) {
  selectedDocId.value = selectedDocId.value === docId ? null : docId
  documentStore.selectDocument(documentStore.documents.find(d => d.id === docId))
}

onMounted(() => {
  documentStore.fetchDocuments()
})
</script>
