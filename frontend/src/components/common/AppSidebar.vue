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
    <el-menu
      :default-active="currentRoute"
      :collapse="false"
      background-color="transparent"
      text-color="var(--text-secondary)"
      active-text-color="var(--text-primary)"
      class="border-none"
      @select="handleSelect"
    >
      <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
        <el-icon class="w-5 h-5 flex-shrink-0">
          <component :is="item.icon" />
        </el-icon>
        <span class="text-sm font-medium">{{ item.label }}</span>
      </el-menu-item>
    </el-menu>

    <!-- Documents section -->
    <div class="px-4 mt-2">
      <h3 class="px-2 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider mb-2">
        我的文档
      </h3>
      <div class="space-y-0.5">
        <div
          v-for="doc in documentStore.documents"
          :key="doc.id"
          class="flex items-center gap-2 px-2 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] rounded cursor-pointer transition-colors"
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
  </aside>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useDocumentStore } from '../../stores/document'
import { useSidebarStore } from '../../stores/sidebar'
import {
  HomeFilled, Upload, Document, Reading, Edit,
  ChatDotSquare, DocumentChecked, TrendCharts, Setting
} from '@element-plus/icons-vue'

const route = useRoute()
const documentStore = useDocumentStore()
const sidebarStore = useSidebarStore()
const selectedDocId = ref(null)

const currentRoute = route.path

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

function handleSelect(index) {
  sidebarStore.close()
}

function toggleDoc(docId) {
  selectedDocId.value = selectedDocId.value === docId ? null : docId
  documentStore.selectDocument(documentStore.documents.find(d => d.id === docId))
}

onMounted(() => {
  documentStore.fetchDocuments()
})
</script>

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
