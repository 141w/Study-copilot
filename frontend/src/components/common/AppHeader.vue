<template>
  <header class="fixed top-0 left-0 right-0 h-16 bg-white border-b border-gray-100 z-50">
    <div class="flex items-center justify-between h-full px-6">
      <div class="flex items-center gap-3">
        <router-link to="/" class="flex items-center gap-2">
          <div class="w-8 h-8 bg-gradient-to-br from-[#ef2cc1] to-[#fc4c02] rounded-lg flex items-center justify-center">
            <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
          </div>
          <span class="text-lg font-semibold text-gray-900">Study Copilot</span>
        </router-link>
      </div>
      
      <div class="flex items-center gap-4">
        <template v-if="authStore.isAuthenticated">
          <span class="text-sm text-gray-600">{{ authStore.user?.username }}</span>
          <button @click="logout" class="text-sm text-gray-500 hover:text-gray-700">
            退出
          </button>
        </template>
        <template v-else>
          <router-link to="/login" class="text-sm text-gray-600 hover:text-gray-900">
            登录
          </router-link>
          <router-link to="/register" class="btn-primary text-sm">
            注册
          </router-link>
        </template>
      </div>
    </div>
  </header>
</template>

<script setup>
import { useAuthStore } from '../../stores/auth'
import { useRouter } from 'vue-router'

const authStore = useAuthStore()
const router = useRouter()

function logout() {
  authStore.logout()
  router.push('/login')
}
</script>