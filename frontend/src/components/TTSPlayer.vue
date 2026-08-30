<template>
  <div class="tts-player inline-flex items-center gap-2">
    <!-- Speak button -->
    <button
      @click="togglePlay"
      :disabled="loading"
      class="inline-flex items-center gap-1.5 px-2 py-1 text-xs rounded-md
             transition-colors duration-200"
      :class="playing
        ? 'bg-indigo-100 text-indigo-700'
        : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]'
      "
      :title="playing ? '停止播放' : '朗读内容'"
    >
      <!-- Loading spinner -->
      <svg v-if="loading" class="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
      <!-- Play icon -->
      <svg v-else-if="!playing" class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
          d="M15.536 8.464a5 5 0 010 7.072M12 6.253v11.494m0 0A7.963 7.963 0 0012 18a7.963 7.963 0 000-4.253M6.343 9.657a8 8 0 1011.314 0" />
      </svg>
      <!-- Stop icon -->
      <svg v-else class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
        <path d="M6 6h12v12H6z" />
      </svg>
      <span>{{ loading ? '生成中...' : playing ? '停止' : '朗读' }}</span>
    </button>

    <!-- Voice selector (optional, shown when showVoiceSelect is true) -->
    <select
      v-if="showVoiceSelect && voices.length > 0"
      v-model="selectedVoice"
      class="text-xs border border-[var(--border-default)] rounded px-1.5 py-0.5 bg-white text-[var(--text-secondary)]
             focus:outline-none focus:ring-1 focus:ring-indigo-300"
    >
      <optgroup v-for="(group, lang) in voiceGroups" :key="lang" :label="lang">
        <option v-for="v in group" :key="v.id" :value="v.id">{{ v.name }}</option>
      </optgroup>
    </select>
  </div>
</template>

<script setup>
import { ref, computed, onBeforeUnmount } from 'vue'
import api from '../services/api'
import { useToastStore } from '../stores/toast'

const props = defineProps({
  text: { type: String, required: true },
  voice: { type: String, default: null },
  showVoiceSelect: { type: Boolean, default: false },
})

const toast = useToastStore()
const loading = ref(false)
const playing = ref(false)
const selectedVoice = ref(props.voice || 'zh-CN-XiaoxiaoNeural')
const voices = ref([])
let audioElement = null
let audioUrl = null

const voiceGroups = computed(() => {
  const groups = {}
  for (const v of voices.value) {
    if (!groups[v.language]) groups[v.language] = []
    groups[v.language].push(v)
  }
  return groups
})

// Load voices on mount if voice selector is shown
async function loadVoices() {
  if (voices.value.length > 0) return
  try {
    const resp = await api.get('/tts/voices')
    const allVoices = resp.data.voices || {}
    voices.value = Object.values(allVoices).flat()
  } catch {
    // Silently fail — voice list is optional
  }
}

// Auto-load voices if selector is shown
if (props.showVoiceSelect) {
  loadVoices()
}

async function togglePlay() {
  if (playing.value) {
    stopPlaying()
    return
  }

  if (!props.text || !props.text.trim()) {
    toast.warning('没有可朗读的内容')
    return
  }

  loading.value = true
  try {
    const resp = await api.post('/tts/generate', {
      text: props.text,
      voice: selectedVoice.value,
      speed: 1.0,
    }, {
      responseType: 'blob',
    })

    // Create audio element from blob
    if (audioUrl) URL.revokeObjectURL(audioUrl)
    audioUrl = URL.createObjectURL(resp.data)

    audioElement = new Audio(audioUrl)
    audioElement.onended = () => {
      playing.value = false
      cleanupAudio()
    }
    audioElement.onerror = () => {
      playing.value = false
      toast.error('音频播放失败')
      cleanupAudio()
    }

    playing.value = true
    await audioElement.play()
  } catch {
    toast.error('语音生成失败，请重试')
    playing.value = false
  } finally {
    loading.value = false
  }
}

function stopPlaying() {
  if (audioElement) {
    audioElement.pause()
    audioElement.currentTime = 0
  }
  playing.value = false
  cleanupAudio()
}

function cleanupAudio() {
  if (audioElement) {
    audioElement = null
  }
  if (audioUrl) {
    URL.revokeObjectURL(audioUrl)
    audioUrl = null
  }
}

onBeforeUnmount(() => {
  stopPlaying()
})
</script>
