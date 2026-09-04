<template>
  <div class="max-w-2xl mx-auto px-6 py-10">
    <!-- 页头：头像 + 用户名 + 注册时间 -->
    <div class="flex items-center gap-5 mb-10">
      <div
        class="w-16 h-16 rounded-xl bg-gradient-to-br from-[var(--color-brand-from)] to-[var(--color-brand-to)]
               flex items-center justify-center text-xl font-semibold text-[var(--text-inverse)] flex-shrink-0"
        aria-hidden="true"
      >
        {{ avatarLetter }}
      </div>
      <div class="min-w-0">
        <h1 class="text-2xl font-semibold text-[var(--text-primary)] truncate">{{ authStore.user?.username }}</h1>
        <p class="text-sm text-[var(--text-muted)] mt-1">注册于 {{ memberSince }}</p>
      </div>
    </div>

    <!-- 资料表单 -->
    <section class="card mb-6">
      <h2 class="text-lg font-semibold text-[var(--text-primary)] mb-1">个人信息</h2>
      <p class="text-sm text-[var(--text-muted)] mb-6">更新你的用户名与邮箱</p>

      <form class="space-y-5" @submit.prevent="handleSaveProfile">
        <div>
          <label for="profile-username" class="block text-sm text-[var(--text-secondary)] mb-1">用户名</label>
          <el-input
            id="profile-username"
            v-model="profileForm.username"
            placeholder="请输入用户名"
            :disabled="profileSaving"
          />
        </div>

        <div>
          <label for="profile-email" class="block text-sm text-[var(--text-secondary)] mb-1">邮箱</label>
          <el-input
            id="profile-email"
            v-model="profileForm.email"
            type="email"
            placeholder="请输入邮箱"
            :disabled="profileSaving"
          />
        </div>

        <p v-if="profileError" class="text-sm text-[var(--color-error)]">{{ profileError }}</p>
        <p v-if="profileSaved" class="text-sm text-[var(--color-success)]">已保存</p>

        <div class="flex justify-end">
          <el-button type="primary" native-type="submit" :loading="profileSaving">
            {{ profileSaving ? '保存中...' : '保存修改' }}
          </el-button>
        </div>
      </form>
    </section>

    <!-- 修改密码 -->
    <section class="card">
      <h2 class="text-lg font-semibold text-[var(--text-primary)] mb-1">修改密码</h2>
      <p class="text-sm text-[var(--text-muted)] mb-6">修改后请使用新密码重新登录</p>

      <form class="space-y-5" @submit.prevent="handleChangePassword">
        <div>
          <label for="profile-old-password" class="block text-sm text-[var(--text-secondary)] mb-1">原密码</label>
          <el-input
            id="profile-old-password"
            v-model="passwordForm.oldPassword"
            type="password"
            show-password
            placeholder="请输入原密码"
            :disabled="passwordSaving"
            required
          />
        </div>

        <div>
          <label for="profile-new-password" class="block text-sm text-[var(--text-secondary)] mb-1">新密码</label>
          <el-input
            id="profile-new-password"
            v-model="passwordForm.newPassword"
            type="password"
            show-password
            placeholder="至少 6 位"
            :disabled="passwordSaving"
            required
          />
        </div>

        <div>
          <label for="profile-confirm-password" class="block text-sm text-[var(--text-secondary)] mb-1">确认新密码</label>
          <el-input
            id="profile-confirm-password"
            v-model="passwordForm.confirmPassword"
            type="password"
            show-password
            placeholder="再次输入新密码"
            :disabled="passwordSaving"
            required
          />
        </div>

        <p v-if="passwordError" class="text-sm text-[var(--color-error)]">{{ passwordError }}</p>
        <p v-if="passwordChanged" class="text-sm text-[var(--color-success)]">密码已更新</p>

        <div class="flex justify-end">
          <el-button type="primary" native-type="submit" :loading="passwordSaving">
            {{ passwordSaving ? '提交中...' : '更新密码' }}
          </el-button>
        </div>
      </form>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '../stores/auth'
import type { AxiosError } from 'axios'

const authStore = useAuthStore()

const profileForm = ref({
  username: '',
  email: ''
})
const profileSaving = ref(false)
const profileError = ref('')
const profileSaved = ref(false)

const passwordForm = ref({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})
const passwordSaving = ref(false)
const passwordError = ref('')
const passwordChanged = ref(false)

/** 头像字母：用户名首字符（大写），兜底 "?"。 */
const avatarLetter = computed(() => {
  const name = authStore.user?.username || ''
  return name.trim().charAt(0).toUpperCase() || '?'
})

/** 注册时间：仅展示年月日，失败回退原文。 */
const memberSince = computed(() => {
  const raw = authStore.user?.created_at
  if (!raw) return '未知时间'
  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) return raw
  return date.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })
})

onMounted(async () => {
  // 刷新一次，保证资料是最新的（本地可能只有登录时的快照）
  try {
    await authStore.fetchUser()
  } catch {
    /* 401 由拦截器统一处理；这里静默展示本地缓存 */
  }
  profileForm.value.username = authStore.user?.username ?? ''
  profileForm.value.email = authStore.user?.email ?? ''
})

async function handleSaveProfile(): Promise<void> {
  profileSaving.value = true
  profileError.value = ''
  profileSaved.value = false

  try {
    await authStore.updateProfile({
      username: profileForm.value.username,
      email: profileForm.value.email
    })
    profileSaved.value = true
  } catch (e) {
    const axiosError = e as AxiosError<{ detail: string }>
    profileError.value = axiosError.response?.data?.detail || '保存失败，请稍后再试'
  } finally {
    profileSaving.value = false
  }
}

async function handleChangePassword(): Promise<void> {
  passwordError.value = ''
  passwordChanged.value = false

  if (passwordForm.value.newPassword.length < 6) {
    passwordError.value = '新密码至少需要 6 位'
    return
  }
  if (passwordForm.value.newPassword !== passwordForm.value.confirmPassword) {
    passwordError.value = '两次输入的新密码不一致'
    return
  }

  passwordSaving.value = true
  try {
    await authStore.changePassword(passwordForm.value.oldPassword, passwordForm.value.newPassword)
    passwordChanged.value = true
    passwordForm.value.oldPassword = ''
    passwordForm.value.newPassword = ''
    passwordForm.value.confirmPassword = ''
  } catch (e) {
    const axiosError = e as AxiosError<{ detail: string }>
    passwordError.value = axiosError.response?.data?.detail || '修改失败，请稍后再试'
  } finally {
    passwordSaving.value = false
  }
}
</script>
