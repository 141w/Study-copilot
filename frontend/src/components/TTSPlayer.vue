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

<script setup>
import { ref, computed, onBeforeUnmount } from 'vue'
import { VideoPlay, VideoPause, Loading } from '@element-plus/icons-vue'
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
