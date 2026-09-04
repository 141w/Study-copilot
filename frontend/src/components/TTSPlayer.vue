<template>
  <div class="tts-player inline-flex items-center gap-2">
    <!-- Speak button -->
    <el-button
      size="small"
      :disabled="loading"
      @click="togglePlay"
      :title="playing ? '停止播放' : '朗读内容'"
    >
      <template #icon>
        <el-icon class="w-3.5 h-3.5" :class="{ 'is-loading': loading }">
          <component :is="loading ? Loading : playing ? VideoPause : VideoPlay" />
        </el-icon>
      </template>
      {{ loading ? '生成中...' : playing ? '停止' : '朗读' }}
    </el-button>

    <!-- Voice selector -->
    <el-select
      v-if="showVoiceSelect && voices.length > 0"
      v-model="selectedVoice"
      size="small"
      placeholder="选择语音"
    >
      <el-option-group
        v-for="(group, lang) in voiceGroups"
        :key="lang"
        :label="lang"
      >
        <el-option
          v-for="v in group"
          :key="v.id"
          :label="v.name"
          :value="v.id"
        />
      </el-option-group>
    </el-select>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { VideoPlay, VideoPause, Loading } from '@/components/icons'
import api from '../services/api'
import { useToastStore } from '../stores/toast'

/** TTS 语音元数据（/tts/voices 响应展平后） */
interface TtsVoice {
  id: string
  name: string
  language: string
}

const props = withDefaults(defineProps<{
  text: string
  voice?: string | null
  showVoiceSelect?: boolean
}>(), {
  voice: null,
  showVoiceSelect: false,
})

const toast = useToastStore()
const loading = ref(false)
const playing = ref(false)
const selectedVoice = ref(props.voice || 'zh-CN-XiaoxiaoNeural')
const voices = ref<TtsVoice[]>([])
let audioElement: HTMLAudioElement | null = null
let audioUrl: string | null = null

const voiceGroups = computed<Record<string, TtsVoice[]>>(() => {
  const groups: Record<string, TtsVoice[]> = {}
  for (const v of voices.value) {
    if (!groups[v.language]) groups[v.language] = []
    groups[v.language].push(v)
  }
  return groups
})

// Load voices on mount if voice selector is shown
// P1-7：setup 顶层直接发请求改为 onMounted（原在组件实例化期发起副作用）
async function loadVoices(): Promise<void> {
  if (voices.value.length > 0) return
  try {
    const resp = await api.get<{ voices: Record<string, TtsVoice[]> }>('/tts/voices')
    const allVoices = resp.data.voices || {}
    voices.value = Object.values(allVoices).flat()
  } catch {
    // Silently fail — voice list is optional
  }
}

onMounted(() => {
  if (props.showVoiceSelect) {
    loadVoices()
  }
})

async function togglePlay(): Promise<void> {
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

function stopPlaying(): void {
  if (audioElement) {
    audioElement.pause()
    audioElement.currentTime = 0
  }
  playing.value = false
  cleanupAudio()
}

function cleanupAudio(): void {
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
