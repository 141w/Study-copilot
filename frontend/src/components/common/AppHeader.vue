<template>
  <header class="fixed top-0 left-0 right-0 h-16 bg-[var(--surface-card)] border-b border-[var(--border-default)] z-50 transition-colors duration-200">
    <div class="flex items-center justify-between h-full px-4 md:px-6">
      <div class="flex items-center gap-3">
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
        <el-button
          circle
          size="small"
          @click="themeStore.toggleTheme()"
          :title="themeStore.isDark ? '切换到亮色模式' : '切换到暗色模式'"
        >
          <el-icon class="w-5 h-5">
            <Sunny v-if="themeStore.isDark" />
            <Moon v-else />
          </el-icon>
        </el-button>

        <template v-if="authStore.isAuthenticated">
          <el-dropdown trigger="click" @command="handleCommand">
            <span class="flex items-center gap-2 cursor-pointer text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
              <el-icon class="w-5 h-5"><User /></el-icon>
              <span class="text-sm hidden md:inline">{{ authStore.user?.username }}</span>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">{{ authStore.user?.username }}</el-dropdown-item>
                <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
        <template v-else>
          <router-link to="/login">
            <el-button text>登录</el-button>
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
import { computed } from 'vue'
import { useAuthStore } from '../../stores/auth'
import { useSidebarStore } from '../../stores/sidebar'
import { useThemeStore } from '../../stores/theme'
import { useRouter } from 'vue-router'
import { User, Sunny, Moon } from '@element-plus/icons-vue'

const authStore = useAuthStore()
const sidebarStore = useSidebarStore()
const themeStore = useThemeStore()
const router = useRouter()

const showSidebar = computed(() => {
  return router.currentRoute.value.path !== '/login' && router.currentRoute.value.path !== '/register'
})

function handleCommand(command) {
  if (command === 'logout') {
    authStore.logout()
    router.push('/login')
  }
}
</script>
