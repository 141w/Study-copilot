<template>
  <div class="min-h-screen flex items-center justify-center bg-[var(--bg-secondary)]">
    <div class="w-full max-w-md">
      <div class="text-center mb-8">
        <div class="login-logo w-12 h-12 bg-gradient-to-br from-[var(--color-brand-from)] to-[var(--color-brand-to)] rounded-2xl flex items-center justify-center mx-auto mb-4">
          <svg class="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
          </svg>
        </div>
        <h1 class="text-2xl font-semibold text-[var(--text-primary)]">登录 Study Copilot</h1>
        <p class="text-[var(--text-muted)] mt-2">使用您的账户登录</p>
      </div>

      <form @submit.prevent="handleLogin">
      <el-card ref="loginCard" class="p-8">
        <div class="space-y-4">
          <div>
            <label for="login-username" class="block text-sm text-[var(--text-secondary)] mb-1">用户名</label>
            <el-input
              id="login-username"
              v-model="form.username"
              placeholder="请输入用户名"
              required
            />
          </div>

          <div>
            <label for="login-password" class="block text-sm text-[var(--text-secondary)] mb-1">密码</label>
            <el-input
              id="login-password"
              v-model="form.password"
              type="password"
              placeholder="请输入密码"
              required
            />
          </div>

          <el-button
            type="primary"
            class="w-full"
            :disabled="loading"
            native-type="submit"
          >
            {{ loading ? '登录中...' : '登录' }}
          </el-button>

          <p v-if="error" class="text-sm text-[var(--color-error)] text-center">{{ error }}</p>
        </div>
      </el-card>
      </form>

      <p class="text-center mt-6 text-[var(--text-muted)]">
        还没有账户?
        <router-link to="/register" class="text-[var(--color-primary)] font-medium hover:underline">
          立即注册
        </router-link>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import gsap from 'gsap'
import { useAuthStore } from '../stores/auth'
import { useRoute, useRouter } from 'vue-router'
import { useConfigStore } from '../stores/config'
import type { AxiosError } from 'axios'

const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()
const configStore = useConfigStore()

const loginCard = ref<HTMLElement | null>(null)
let ctx: gsap.Context | null = null

const form = ref({
  username: '',
  password: ''
})
const loading = ref(false)
const error = ref('')

async function handleLogin(): Promise<void> {
  loading.value = true
  error.value = ''

  try {
    await authStore.login(form.value.username, form.value.password)
    await configStore.syncToChatStore()
    // 回跳到登录前想访问的页面；无记录则回首页（P0-3）
    const redirect = route.query.redirect
    router.push(typeof redirect === 'string' && redirect.startsWith('/') ? redirect : '/')
  } catch (e) {
    const axiosError = e as AxiosError<{ detail: string }>
    error.value = axiosError.response?.data?.detail || '登录失败，请检查用户名和密码'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  ctx = gsap.context(() => {
    // 卡片容器：el-card 根节点（loginCard 绑定到 el-card 的 DOM）
    if (loginCard.value) {
      gsap.from(loginCard.value, {
        y: 30,
        opacity: 0,
        duration: 0.6,
        ease: 'power2.out'
      })
    }

    const logoEl = document.querySelector('.login-logo')
    if (logoEl) {
      gsap.from(logoEl, {
        scale: 0,
        duration: 0.6,
        ease: 'back.out(1.7)'
      })
    }
  })
})

onUnmounted(() => {
  ctx?.revert()
})
</script>