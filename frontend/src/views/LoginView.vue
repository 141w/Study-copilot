<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50">
    <div class="w-full max-w-md">
      <div class="text-center mb-8">
        <div class="w-12 h-12 bg-gradient-to-br from-[#ef2cc1] to-[#fc4c02] rounded-xl flex items-center justify-center mx-auto mb-4">
          <svg class="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
          </svg>
        </div>
        <h1 class="text-2xl font-semibold text-gray-900">登录 Study Copilot</h1>
        <p class="text-gray-500 mt-2">使用您的账户登录</p>
      </div>
      
      <form @submit.prevent="handleLogin" class="card p-8">
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">用户名</label>
            <input
              v-model="form.username"
              type="text"
              class="input-field"
              placeholder="请输入用户名"
              required
            />
          </div>
          
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">密码</label>
            <input
              v-model="form.password"
              type="password"
              class="input-field"
              placeholder="请输入密码"
              required
            />
          </div>
          
          <button
            type="submit"
            :disabled="loading"
            class="w-full btn-primary py-3"
          >
            {{ loading ? '登录中...' : '登录' }}
          </button>
          
          <p v-if="error" class="text-sm text-red-500 text-center">{{ error }}</p>
        </div>
      </form>
      
      <p class="text-center mt-6 text-gray-500">
        还没有账户?
        <router-link to="/register" class="text-[#010120] font-medium hover:underline">
          立即注册
        </router-link>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useRouter } from 'vue-router'
import { useConfigStore } from '../stores/config'
import { useChatStore } from '../stores/chat'

const authStore = useAuthStore()
const router = useRouter()
const configStore = useConfigStore()
const chatStore = useChatStore()

const form = ref({
  username: '',
  password: ''
})
const loading = ref(false)
const error = ref('')

async function handleLogin() {
  loading.value = true
  error.value = ''

  try {
    await authStore.login(form.value.username, form.value.password)
    await configStore.syncToChatStore()
    router.push('/')
  } catch (e) {
    error.value = e.response?.data?.detail || '登录失败，请检查用户名和密码'
  } finally {
    loading.value = false
  }
}
</script>