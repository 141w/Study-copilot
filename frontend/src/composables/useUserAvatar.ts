import { computed, type ComputedRef } from 'vue'
import { useAuthStore } from '@/stores/auth'

/**
 * 用户头像派生状态。
 *
 * 首字母规则此前在 AppHeader 与 ProfileView 各写一份（靠复制维持一致），
 * 现统一到此处的纯函数；它与 store 解耦，便于直接单测。
 */

/** 头像首字母：用户名去空白后首字符大写；空/纯空白兜底 '?' */
export function resolveAvatarLetter(username?: string | null): string {
  return (username || '').trim().charAt(0).toUpperCase() || '?'
}

export interface UserAvatarState {
  /** 首字母渐变头像的字符（AppHeader / ProfileView 共用口径） */
  avatarLetter: ComputedRef<string>
}

/** 从 auth store 派生头像展示值，随登录用户变化自动更新 */
export function useUserAvatar(): UserAvatarState {
  const authStore = useAuthStore()

  const avatarLetter = computed(() => resolveAvatarLetter(authStore.user?.username))

  return { avatarLetter }
}
