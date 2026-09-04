<template>
  <header class="fixed top-0 left-0 right-0 h-[var(--layout-header-height)] bg-[var(--surface-card)] border-b border-[var(--border-default)] z-50 transition-colors duration-200">
    <div class="flex items-center justify-between h-full px-4 md:px-6">
      <div class="flex items-center gap-3">
        <button
          v-if="showSidebar"
          aria-label="打开菜单"
          class="md:hidden p-2 -ml-2 text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          @click="sidebarStore.toggle()"
        >
          <el-icon class="w-6 h-6"><Fold /></el-icon>
        </button>
        <router-link to="/" class="flex items-center gap-2">
          <CopilotBotAvatar :size="48" mood="idle" />
          <span class="text-lg font-semibold text-[var(--text-primary)] hidden sm:inline">Study Copilot</span>
        </router-link>
      </div>

      <div class="flex items-center gap-2 md:gap-4">
        <el-button
          circle
          size="small"
          aria-label="切换主题"
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
            <span
              class="flex items-center gap-2 cursor-pointer rounded-md px-1.5 py-1 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition-colors"
              aria-label="用户菜单"
            >
              <!-- 批次4：真实头像——用户名首字 + 品牌渐变，替代裸图标 -->
              <span
                class="w-7 h-7 rounded-full bg-gradient-to-br from-[var(--color-brand-from)] to-[var(--color-brand-to)]
                       flex items-center justify-center text-xs font-semibold text-[var(--text-inverse)] flex-shrink-0"
                aria-hidden="true"
              >{{ avatarLetter }}</span>
              <span class="text-sm hidden md:inline">{{ authStore.user?.username }}</span>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">
                  <el-icon class="mr-1"><User /></el-icon>个人设置
                </el-dropdown-item>
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

<script setup lang="ts">
import { computed } from 'vue'
import { useAuthStore } from '../../stores/auth'
import { useSidebarStore } from '../../stores/sidebar'
import { useThemeStore } from '../../stores/theme'
import { useRouter } from 'vue-router'
import { User, Sunny, Moon, Fold } from '@/components/icons'
import CopilotBotAvatar from '@/components/CopilotBotAvatar.vue'

const authStore = useAuthStore()
const sidebarStore = useSidebarStore()
const themeStore = useThemeStore()
const router = useRouter()

/** 批次4：头像首字符（用户名首字大写，兜底 "?"） */
const avatarLetter = computed(() => {
  const name = authStore.user?.username || ''
  return name.trim().charAt(0).toUpperCase() || '?'
})

const showSidebar = computed(() => {
  return router.currentRoute.value.path !== '/login' && router.currentRoute.value.path !== '/register'
})

function handleCommand(command: string | number | object): void {
  if (command === 'profile') {
    router.push('/profile')
  } else if (command === 'logout') {
    authStore.logout()
    router.push('/login')
  }
}
</script>
