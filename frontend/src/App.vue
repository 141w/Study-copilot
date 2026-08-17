<template>
  <div class="min-h-screen bg-[var(--bg-primary)] transition-colors duration-200">
    <AppHeader />
    <div class="flex pt-16">
      <AppSidebar v-if="showSidebar" />
      <main class="flex-1 min-w-0" :class="showSidebar ? 'md:ml-64' : ''">
        <router-view v-slot="{ Component }">
          <keep-alive :include="['QuizView', 'ChatView', 'AnalysisView']">
            <Transition name="page">
              <component :is="Component" />
            </Transition>
          </keep-alive>
        </router-view>
      </main>
    </div>
    <Toast />
  </div>
</template>

<script setup>
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useSidebarStore } from './stores/sidebar'
import AppHeader from './components/common/AppHeader.vue'
import AppSidebar from './components/common/AppSidebar.vue'
import Toast from './components/common/Toast.vue'

const route = useRoute()
const sidebarStore = useSidebarStore()

const showSidebar = computed(() => {
  return route.path !== '/login' && route.path !== '/register'
})

// Close sidebar on route change (mobile UX)
watch(() => route.path, () => {
  sidebarStore.close()
})
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
</style>
