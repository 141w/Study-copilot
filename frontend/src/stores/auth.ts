import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../services/api'
import router from '../router'
import type { User, AuthTokens } from '../types/models'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const token = ref<string | null>(localStorage.getItem('token') || null)
  const refreshToken = ref<string | null>(localStorage.getItem('refreshToken') || null)

  const isAuthenticated = computed(() => !!token.value)

  async function login(username: string, password: string): Promise<AuthTokens> {
    const params = new URLSearchParams()
    params.append('username', username)
    params.append('password', password)

    const response = await api.post<AuthTokens>('/auth/login', params)

    token.value = response.data.access_token
    refreshToken.value = response.data.refresh_token
    localStorage.setItem('token', token.value)
    localStorage.setItem('refreshToken', refreshToken.value)

    await fetchUser()

    return response.data
  }

  async function register(username: string, email: string, password: string): Promise<User> {
    const response = await api.post<User>('/auth/register', {
      username,
      email,
      password
    })

    return response.data
  }

  async function fetchUser(): Promise<void> {
    if (!token.value) return

    try {
      const response = await api.get<User>('/auth/me')
      user.value = response.data
    } catch (error) {
      logout()
    }
  }

  function logout(): void {
    token.value = null
    refreshToken.value = null
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('refreshToken')
    router.push('/login')
  }

  /**
   * 更新当前用户资料（用户名/邮箱）。后端未提供的字段（undefined）保持不变；
   * 成功后同步本地 user 状态。
   */
  async function updateProfile(payload: { username?: string; email?: string }): Promise<User> {
    const response = await api.put<User>('/auth/me', payload)
    user.value = response.data
    return response.data
  }

  /**
   * 修改密码：需提供原密码，新密码 ≥ 6 位（后端校验）。
   */
  async function changePassword(oldPassword: string, newPassword: string): Promise<void> {
    await api.put('/auth/password', {
      old_password: oldPassword,
      new_password: newPassword
    })
  }

  if (token.value) {
    fetchUser()
  }

  return {
    user,
    token,
    refreshToken,
    isAuthenticated,
    login,
    register,
    fetchUser,
    updateProfile,
    changePassword,
    logout
  }
})
