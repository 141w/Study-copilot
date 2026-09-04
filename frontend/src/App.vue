<template>
  <div class="min-h-screen bg-[var(--bg-primary)] transition-colors duration-200">
    <AppHeader v-if="showHeader" />
    <div class="flex" :class="showHeader ? 'pt-[var(--layout-header-height)]' : ''">
      <AppSidebar v-if="showSidebar" />
      <main class="flex-1 min-w-0" :class="showSidebar ? 'md:ml-[var(--layout-sidebar-width)]' : ''">
        <router-view v-slot="{ Component }">
          <keep-alive :include="['QuizView', 'ChatView', 'AnalysisView']">
            <Transition name="page">
              <component :is="Component" />
            </Transition>
          </keep-alive>
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useSidebarStore } from './stores/sidebar'
import AppHeader from './components/common/AppHeader.vue'
import AppSidebar from './components/common/AppSidebar.vue'

const route = useRoute()
const sidebarStore = useSidebarStore()

// 登录/注册页沉浸式布局：隐藏顶部 header 与侧栏
const isAuthPage = computed(() => route.path === '/login' || route.path === '/register')
const showHeader = computed(() => !isAuthPage.value)
const showSidebar = computed(() => !isAuthPage.value)

// Close sidebar on route change (mobile UX)
watch(
  () => route.path,
  () => {
    sidebarStore.close()
  }
)
</script>

<style>
.page-enter-active,
.page-leave-active {
  transition: all 0.2s ease;
}

.page-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.page-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* P1-1（§6.B）：减少动态偏好下页面切换降级为瞬时 */
@media (prefers-reduced-motion: reduce) {
  .page-enter-active,
  .page-leave-active {
    transition: none;
  }
  .page-enter-from,
  .page-leave-to {
    opacity: 1;
    transform: none;
  }
}
</style>
