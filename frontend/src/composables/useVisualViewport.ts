import { ref, onMounted, onUnmounted, computed } from 'vue'

export function useVisualViewport() {
  const viewportHeight = ref(typeof window !== 'undefined' ? window.innerHeight : 0)
  const isKeyboardOpen = ref(false)
  const keyboardHeight = ref(0)

  function updateViewport(): void {
    if (typeof window === 'undefined') return
    const vv = window.visualViewport
    if (!vv) {
      viewportHeight.value = window.innerHeight
      return
    }

    viewportHeight.value = vv.height
    const offset = window.innerHeight - vv.height
    keyboardHeight.value = offset > 100 ? offset : 0
    isKeyboardOpen.value = keyboardHeight.value > 0
  }

  onMounted(() => {
    if (typeof window === 'undefined') return
    updateViewport()
    const vv = window.visualViewport
    if (vv) {
      vv.addEventListener('resize', updateViewport, { passive: true })
      vv.addEventListener('scroll', updateViewport, { passive: true })
    } else {
      window.addEventListener('resize', updateViewport, { passive: true })
    }
  })

  onUnmounted(() => {
    if (typeof window === 'undefined') return
    const vv = window.visualViewport
    if (vv) {
      vv.removeEventListener('resize', updateViewport)
      vv.removeEventListener('scroll', updateViewport)
    } else {
      window.removeEventListener('resize', updateViewport)
    }
  })

  const containerHeightStyle = computed(() => {
    // 扣除顶部 header 高度 4rem (64px)
    if (viewportHeight.value > 0) {
      return { height: `${viewportHeight.value - 64}px` }
    }
    return { height: 'calc(100dvh - 4rem)' }
  })

  return {
    viewportHeight,
    isKeyboardOpen,
    keyboardHeight,
    containerHeightStyle,
  }
}
