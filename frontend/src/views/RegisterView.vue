<template>
  <div class="min-h-screen flex items-center justify-center bg-[var(--bg-secondary)]">
    <div class="w-full max-w-md">
      <div class="text-center mb-8">
        <div class="w-12 h-12 bg-gradient-to-br from-[var(--color-brand-from)] to-[var(--color-brand-to)] rounded-xl flex items-center justify-center mx-auto mb-4">
          <el-icon class="w-8 h-8 text-[var(--text-inverse)]"><Reading /></el-icon>
        </div>
        <h1 class="text-2xl font-semibold text-[var(--text-primary)]">注册 Study Copilot</h1>
        <p class="text-[var(--text-muted)] mt-2">创建您的账户</p>
      </div>

      <form @submit.prevent="handleRegister">
      <el-card :body-style="{ padding: '32px' }">
        <div class="space-y-4">
          <div>
            <label for="register-username" class="block text-sm font-medium text-[var(--text-secondary)] mb-1">用户名</label>
            <el-input
              id="register-username"
              v-model="form.username"
              placeholder="请输入用户名"
              required
            />
          </div>

          <div>
            <label for="register-email" class="block text-sm font-medium text-[var(--text-secondary)] mb-1">邮箱</label>
            <el-input
              id="register-email"
              v-model="form.email"
              type="email"
              placeholder="请输入邮箱"
              required
            />
          </div>

          <div>
            <label for="register-password" class="block text-sm font-medium text-[var(--text-secondary)] mb-1">密码</label>
            <el-input
              id="register-password"
              v-model="form.password"
              type="password"
              placeholder="请输入密码"
              required
            />
          </div>

          <el-button
            type="primary"
            class="w-full"
            :loading="loading"
            native-type="submit"
          >
            {{ loading ? '注册中...' : '注册' }}
          </el-button>

          <p v-if="error" class="text-sm text-[var(--color-error)] text-center">{{ error }}</p>
        </div>
      </el-card>
      </form>

      <p class="text-center mt-6 text-[var(--text-muted)]">
        已有账户?
        <router-link to="/login" class="text-[var(--color-primary)] font-medium hover:underline">
          立即登录
        </router-link>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Reading } from '@/components/icons'
import { useAuthStore } from '../stores/auth'
import { useRouter } from 'vue-router'
import type { AxiosError } from 'axios'

const authStore = useAuthStore()
const router = useRouter()

const form = ref({
  username: '',
  email: '',
  password: ''
})
const loading = ref(false)
const error = ref('')

async function handleRegister(): Promise<void> {
  loading.value = true
  error.value = ''

  try {
    await authStore.register(form.value.username, form.value.email, form.value.password)
    router.push('/login')
  } catch (e) {
    const axiosError = e as AxiosError<{ detail: string }>
    error.value = axiosError.response?.data?.detail || '注册失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
</script>