import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../services/api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const token = ref(localStorage.getItem('token') || null)
  const refreshToken = ref(localStorage.getItem('refreshToken') || null)
  
  const isAuthenticated = computed(() => !!token.value)
  
  async function login(username, password) {
    const formData = new FormData()
    formData.append('username', username)
    formData.append('password', password)
    
    const response = await api.post('/auth/login', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    
    token.value = response.data.access_token
    refreshToken.value = response.data.refresh_token
    localStorage.setItem('token', token.value)
    localStorage.setItem('refreshToken', refreshToken.value)
    
    await fetchUser()
    
    return response.data
  }
  
  async function register(username, email, password) {
    const response = await api.post('/auth/register', {
      username,
      email,
      password
    })
    
    return response.data
  }
  
  async function fetchUser() {
    if (!token.value) return
    
    try {
      const response = await api.get('/auth/me')
      user.value = response.data
    } catch (error) {
      logout()
    }
  }
  
  function logout() {
    token.value = null
    refreshToken.value = null
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('refreshToken')
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
    logout
  }
})