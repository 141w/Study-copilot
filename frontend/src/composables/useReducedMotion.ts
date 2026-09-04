import { ref, readonly, onMounted, onUnmounted, type Ref } from 'vue'

/**
 * P1-1（design-taste-frontend §6.B）：prefers-reduced-motion 响应式降级。
 *
 * 所有 GSAP/CSS 动画入口应先检查 prefersReduced，为 true 时跳过动画，
 * 保证前庭障碍用户与"减少动态"系统设置被尊重。
 *
 * 用法：
 *   const { prefersReduced } = useReducedMotion()
 *   if (prefersReduced.value) return
 *   gsap.from(...)
 *
 * 组件挂载后监听系统设置变化（用户在系统设置里切换即刻生效）；
 * SSR 与老旧浏览器安全降级为 false（jsdom 环境为 true，测试中不产生动画）。
 */
export function useReducedMotion(): { prefersReduced: Readonly<Ref<boolean>> } {
  const reduced = ref(false)
  let mql: MediaQueryList | null = null
  const handler = (e: MediaQueryListEvent): void => { reduced.value = e.matches }

  onMounted(() => {
    if (typeof window.matchMedia !== 'function') return
    mql = window.matchMedia('(prefers-reduced-motion: reduce)')
    reduced.value = mql.matches
    if (typeof mql.addEventListener === 'function') {
      mql.addEventListener('change', handler)
    } else if (typeof mql.addListener === 'function') {
      // Safari < 14 兼容
      mql.addListener(handler)
    }
  })

  onUnmounted(() => {
    if (!mql) return
    if (typeof mql.removeEventListener === 'function') {
      mql.removeEventListener('change', handler)
    } else if (typeof mql.removeListener === 'function') {
      mql.removeListener(handler)
    }
    mql = null
  })

  return { prefersReduced: readonly(reduced) }
}
