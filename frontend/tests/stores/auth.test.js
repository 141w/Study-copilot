import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock the api module
vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

// Mock the router
vi.mock('@/router', () => ({
  default: {
    push: vi.fn(),
  },
}))

import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import api from '@/services/api'
import router from '@/router'

describe('Auth Store', () => {
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useAuthStore()
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('has correct initial state when no token stored', () => {
    expect(store.user).toBeNull()
    expect(store.token).toBeNull()
    expect(store.isAuthenticated).toBe(false)
  })

  it('login stores token and fetches user', async () => {
    const loginResponse = {
      data: {
        access_token: 'test-token',
        refresh_token: 'test-refresh',
      },
    }
    const userResponse = {
      data: { id: 1, username: 'testuser', email: 'test@example.com' },
    }
    api.post.mockResolvedValue(loginResponse)
    api.get.mockResolvedValue(userResponse)

    await store.login('testuser', 'password123')

    expect(store.token).toBe('test-token')
    expect(store.refreshToken).toBe('test-refresh')
    expect(store.isAuthenticated).toBe(true)
    expect(store.user).toEqual(userResponse.data)
    expect(localStorage.setItem).toHaveBeenCalledWith('token', 'test-token')
    expect(localStorage.setItem).toHaveBeenCalledWith('refreshToken', 'test-refresh')
  })

  it('register sends correct data to API', async () => {
    const registerResponse = { data: { id: 1, username: 'newuser' } }
    api.post.mockResolvedValue(registerResponse)

    const result = await store.register('newuser', 'new@example.com', 'pass123')

    expect(api.post).toHaveBeenCalledWith('/auth/register', {
      username: 'newuser',
      email: 'new@example.com',
      password: 'pass123',
    })
    expect(result).toEqual(registerResponse.data)
  })

  it('logout clears state and redirects', () => {
    // Set some state first
    store.token = 'some-token'
    store.refreshToken = 'some-refresh'
    store.user = { id: 1, username: 'user' }

    store.logout()

    expect(store.token).toBeNull()
    expect(store.refreshToken).toBeNull()
    expect(store.user).toBeNull()
    expect(store.isAuthenticated).toBe(false)
    expect(localStorage.removeItem).toHaveBeenCalledWith('token')
    expect(localStorage.removeItem).toHaveBeenCalledWith('refreshToken')
    expect(router.push).toHaveBeenCalledWith('/login')
  })
})
