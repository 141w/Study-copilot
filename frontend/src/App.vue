<template>
  <div class="min-h-screen bg-white">
    <AppHeader />
    <div class="flex pt-16">
      <AppSidebar v-if="showSidebar" />
      <main class="flex-1" :class="showSidebar ? 'ml-64' : ''">
        <router-view v-slot="{ Component }">
          <keep-alive :include="['QuizView', 'ChatView', 'AnalysisView']">
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </main>
    </div>
    <Toast />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from './components/common/AppHeader.vue'
import AppSidebar from './components/common/AppSidebar.vue'
import Toast from './components/common/Toast.vue'

const route = useRoute()
const showSidebar = computed(() => {
  return route.path !== '/login' && route.path !== '/register'
})
</script>

<style>
html, body {
  font-family: 'Outfit', sans-serif;
}
</style>