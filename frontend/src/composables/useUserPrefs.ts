import { ref } from 'vue'

export type AvatarType = 'letter' | 'bot' | 'custom'
export type AIStyle = 'rigorous' | 'balanced' | 'concise'

export interface UserPreferences {
  avatarType: AvatarType
  customAvatar: string // Base64 data URL
  bio: string
  defaultChoiceCount: number
  defaultShortCount: number
  aiStyle: AIStyle
  botGaze: boolean
  botIdleSleep: boolean
}

const PREFS_KEY = 'study_copilot_user_prefs'

const defaultPreferences: UserPreferences = {
  avatarType: 'letter',
  customAvatar: '',
  bio: '让每一份学习资料都被充分理解',
  defaultChoiceCount: 5,
  defaultShortCount: 2,
  aiStyle: 'balanced',
  botGaze: true,
  botIdleSleep: true
}

// 全局单例响应式状态，保证跨组件数据一致
const globalPrefs = ref<UserPreferences>({ ...defaultPreferences })
let initialized = false

function init(): void {
  if (initialized || typeof window === 'undefined') return
  try {
    const raw = localStorage.getItem(PREFS_KEY)
    if (raw) {
      globalPrefs.value = { ...defaultPreferences, ...JSON.parse(raw) }
    }
  } catch (e) {
    console.warn('Failed to load user preferences from localStorage:', e)
  }
  initialized = true
}

export function useUserPrefs() {
  init()

  function savePreferences(newPrefs?: Partial<UserPreferences>): void {
    if (newPrefs) {
      globalPrefs.value = { ...globalPrefs.value, ...newPrefs }
    }
    try {
      localStorage.setItem(PREFS_KEY, JSON.stringify(globalPrefs.value))
    } catch (e) {
      console.warn('Failed to save user preferences:', e)
    }
  }

  function setCustomAvatar(base64Data: string): void {
    globalPrefs.value.customAvatar = base64Data
    globalPrefs.value.avatarType = 'custom'
    savePreferences()
  }

  function removeCustomAvatar(): void {
    globalPrefs.value.customAvatar = ''
    globalPrefs.value.avatarType = 'letter'
    savePreferences()
  }

  return {
    prefs: globalPrefs,
    savePreferences,
    setCustomAvatar,
    removeCustomAvatar
  }
}
