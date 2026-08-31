<template>
  <header class="fixed top-0 left-0 right-0 h-16 bg-[var(--surface-card)] border-b border-[var(--border-default)] z-50 transition-colors duration-200">
    <div class="flex items-center justify-between h-full px-4 md:px-6">
      <div class="flex items-center gap-3">
        <!-- Hamburger menu button (mobile only) -->
        <button
          v-if="showSidebar"
          class="md:hidden p-2 -ml-2 text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          @click="sidebarStore.toggle()"
        >
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <router-link to="/" class="flex items-center gap-2">
          <div class="w-8 h-8 bg-gradient-to-br from-[#ef2cc1] to-[#fc4c02] rounded-lg flex items-center justify-center">
            <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
          </div>
          <span class="text-lg font-semibold text-[var(--text-primary)] hidden sm:inline">Study Copilot</span>
        </router-link>
      </div>

      <div class="flex items-center gap-2 md:gap-4">
        <!-- Theme toggle button -->
        <button
          @click="themeStore.toggleTheme()"
          class="p-2 rounded-lg text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition-colors"
          :title="themeStore.isDark ? '切换到亮色模式' : '切换到暗色模式'"
        >
          <!-- Sun icon (show in dark mode) -->
          <svg v-if="themeStore.isDark" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
          </svg>
          <!-- Moon icon (show in light mode) -->
          <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
          </svg>
        </button>

        <template v-if="authStore.isAuthenticated">
          <!-- Desktop user info -->
          <div class="hidden md:flex items-center gap-4">
            <span class="text-sm text-[var(--text-secondary)]">{{ authStore.user?.username }}</span>
            <button @click="logout" class="text-sm text-[var(--text-muted)] hover:text-[var(--text-primary)]">
              退出
            </button>
          </div>

          <!-- Mobile user menu -->
          <div class="md:hidden relative" ref="userMenuRef">
            <button
              @click="showUserMenu = !showUserMenu"
              class="p-2 rounded-lg text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
            </button>

            <Transition name="dropdown">
              <div
                v-if="showUserMenu"
                class="absolute right-0 top-full mt-2 w-48 bg-[var(--surface-card)] border border-[var(--border-default)] rounded-lg shadow-lg py-2"
              >
                <div class="px-4 py-2 border-b border-[var(--border-default)]">
                  <p class="text-sm font-medium text-[var(--text-primary)]">{{ authStore.user?.username }}</p>
                </div>
                <button
                  @click="logout"
                  class="w-full text-left px-4 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
                >
                  退出登录
                </button>
              </div>
            </Transition>
          </div>
        </template>
        <template v-else>
          <router-link to="/login" class="text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
            登录
          </router-link>
          <router-link to="/register">
            <el-button type="primary" size="small">注册</el-button>
          </router-link>
        </template>
      </div>
    </div>
  </header>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '../../stores/auth'
import { useSidebarStore } from '../../stores/sidebar'
import { useThemeStore } from '../../stores/theme'
import { useRouter } from 'vue-router'

const authStore = useAuthStore()
const sidebarStore = useSidebarStore()
const themeStore = useThemeStore()
const router = useRouter()

const showSidebar = computed(() => {
  return router.currentRoute.value.path !== '/login' && router.currentRoute.value.path !== '/register'
})

const showUserMenu = ref(false)
const userMenuRef = ref(null)

function logout() {
  showUserMenu.value = false
  authStore.logout()
  router.push('/login')
}

// Close user menu when clicking outside
function handleClickOutside(event) {
  if (userMenuRef.value && !userMenuRef.value.contains(event.target)) {
    showUserMenu.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
.dropdown-enter-active,
.dropdown-leave-active {
  transition: all 0.2s ease;
}

.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
