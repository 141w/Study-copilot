import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useSidebarStore = defineStore('sidebar', () => {
  const isOpen = ref(false)

  function toggle(): void {
    isOpen.value = !isOpen.value
  }

  function open(): void {
    isOpen.value = true
  }

  function close(): void {
    isOpen.value = false
  }

  return { isOpen, toggle, open, close }
})
