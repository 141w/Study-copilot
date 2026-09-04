<template>
  <!-- Backdrop overlay for mobile sidebar -->
  <Transition name="fade">
    <div
      v-if="sidebarStore.isOpen"
      class="fixed inset-0 bg-[var(--surface-overlay)] z-30 md:hidden"
      @click="sidebarStore.close()"
    ></div>
  </Transition>

  <aside
    class="fixed left-0 top-[var(--layout-header-height)] bottom-0 w-[var(--layout-sidebar-width)] z-40
           transition-transform duration-300 ease-in-out
           md:translate-x-0"
    :class="sidebarStore.isOpen ? 'translate-x-0' : '-translate-x-full'"
    style="background: var(--gradient-sidebar); box-shadow: 1px 0 0 var(--border-default);"
  >
    <el-menu
      :default-active="currentRoute"
      :collapse="false"
      :router="true"
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
      <!-- 批次7：文档多时列表溢出侧栏（原无上限渲染）——限高 + 内部滚动 -->
      <div class="space-y-0.5 max-h-[30vh] overflow-y-auto overscroll-contain">
        <div
          v-for="doc in documentStore.documents"
          :key="doc.id"
          role="button"
          tabindex="0"
          :aria-label="`选择文档 ${doc.filename}`"
          class="flex items-center gap-2 px-2 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] rounded cursor-pointer transition-colors"
          :class="{ 'bg-[var(--bg-hover)]': doc.id === selectedDocId }"
          @click="toggleDoc(doc.id)"
          @keydown.enter.prevent="toggleDoc(doc.id)"
          @keydown.space.prevent="toggleDoc(doc.id)"
        >
          <el-icon class="w-4 h-4 text-[var(--text-muted)] flex-shrink-0">
            <Document />
          </el-icon>
          <span class="truncate flex-1">{{ doc.filename }}</span>
        </div>      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useDocumentStore } from '../../stores/document'
import { useSidebarStore } from '../../stores/sidebar'
import type { Document as DocumentModel } from '../../types/models'
import {
  HomeFilled, Upload, Document, Reading, Edit,
  ChatDotSquare, DocumentChecked, TrendCharts, Setting, List
} from '@/components/icons'
import type { Component } from 'vue'

const route = useRoute()
const documentStore = useDocumentStore()
const sidebarStore = useSidebarStore()

const currentRoute = computed(() => route.path)

// P3-2：高亮态直接派生自 store（单一来源），外部视图选文档时侧栏自动联动
const selectedDocId = computed(() => documentStore.currentDocument?.id ?? null)

interface MenuItem {
  path: string
  label: string
  icon: Component
}

const menuItems: MenuItem[] = [
  { path: '/', label: '首页', icon: HomeFilled },
  { path: '/upload', label: '上传文档', icon: Upload },
  { path: '/documents', label: '文档阅读', icon: Document },
  { path: '/courses', label: '课程空间', icon: Reading },
  { path: '/notes', label: '笔记', icon: Edit },
  { path: '/chat', label: 'AI问答', icon: ChatDotSquare },
  { path: '/quiz', label: '做题练习', icon: DocumentChecked },
  { path: '/analysis', label: '学习分析', icon: TrendCharts },
  { path: '/model-config', label: '模型配置', icon: Setting },
  // P3-2：后台任务入口（原侧栏缺失，TasksView 只能 URL 直达）
  { path: '/tasks', label: '后台任务', icon: List }
]

function handleSelect(_index: string): void {
  sidebarStore.close()
}

function toggleDoc(docId: string): void {
  const doc: DocumentModel | undefined = documentStore.documents.find(d => d.id === docId)
  if (!doc) return
  // P3-2：选中态由 store 派生，这里只写 store
  if (documentStore.currentDocument?.id === docId) {
    documentStore.selectDocument(null)
  } else {
    documentStore.selectDocument(doc)
  }
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
