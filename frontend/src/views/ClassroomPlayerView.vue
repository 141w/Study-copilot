<template>
  <div
    ref="playerContainer"
    class="h-screen w-screen max-h-screen overflow-hidden bg-[var(--bg-primary)] text-[var(--text-primary)] flex flex-col select-none relative font-sans"
  >
    <!-- 顶栏宿主控制条 (Study Copilot Host Header) -->
    <header class="h-12 px-3 sm:px-5 bg-[var(--surface-card)]/90 backdrop-blur-md border-b border-[var(--border-default)] flex items-center justify-between z-30 flex-shrink-0 shadow-sm">
      <!-- 左侧：返回、微课标识、课程标题与参考文档 -->
      <div class="flex items-center gap-2.5 sm:gap-3 min-w-0">
        <el-button
          circle
          size="small"
          @click="goBack"
          title="返回课程"
          class="!border-[var(--border-default)] hover:!border-[var(--color-primary)]"
        >
          <el-icon><ArrowLeft /></el-icon>
        </el-button>

        <div class="min-w-0 flex items-center gap-2 sm:gap-2.5">
          <span class="text-[11px] px-2.5 py-0.5 rounded-full bg-[var(--color-primary-light)] text-[var(--color-primary)] font-semibold flex-shrink-0 border border-[var(--border-default)]">
            AI 互动微课
          </span>
          <h1 class="text-xs sm:text-sm font-semibold truncate text-[var(--text-primary)] max-w-[140px] sm:max-w-xs md:max-w-md" :title="courseTitle">
            {{ courseTitle }}
          </h1>

          <!-- 参考文档气泡 -->
          <el-popover
            v-if="sourceDocuments.length > 0"
            placement="bottom-start"
            :width="300"
            trigger="hover"
          >
            <template #reference>
              <span
                class="text-[11px] px-2 py-0.5 rounded-full bg-[var(--color-success-light)] text-[var(--color-success)] font-medium hidden md:inline-flex items-center gap-1 border border-[var(--color-success)]/20 cursor-pointer hover:opacity-85 transition-opacity"
              >
                <el-icon class="w-3 h-3"><Tickets /></el-icon>
                {{ sourceDocuments.length }} 份参考文档
              </span>
            </template>
            <div class="p-1 space-y-2">
              <div class="text-xs font-semibold text-[var(--text-primary)] border-b border-[var(--border-default)] pb-1.5 flex items-center justify-between">
                <span>微课引用参考文档</span>
                <span class="text-[10px] text-[var(--text-muted)] font-mono">共 {{ sourceDocuments.length }} 篇</span>
              </div>
              <div class="max-h-48 overflow-y-auto space-y-1.5 pr-1">
                <div
                  v-for="(doc, idx) in sourceDocuments"
                  :key="doc.id || idx"
                  class="text-xs text-[var(--text-secondary)] flex items-center gap-1.5 truncate p-1 rounded hover:bg-[var(--bg-secondary)]"
                  :title="doc.filename"
                >
                  <el-icon class="text-[var(--color-primary)] flex-shrink-0"><Document /></el-icon>
                  <span class="truncate flex-1">{{ doc.filename || '未命名文档' }}</span>
                  <span v-if="doc.file_size" class="text-[10px] text-[var(--text-muted)] font-mono flex-shrink-0">
                    {{ formatSize(doc.file_size) }}
                  </span>
                </div>
              </div>
            </div>
          </el-popover>
        </div>
      </div>

      <!-- 右侧控制组：设置、独立窗口打开、全屏、退出 -->
      <div class="flex items-center gap-1.5 sm:gap-2">
        <el-button
          circle
          size="small"
          @click="settingsVisible = true"
          title="微课设置"
          class="!border-[var(--border-default)] hover:!border-[var(--color-primary)]"
        >
          <el-icon><Setting /></el-icon>
        </el-button>

        <el-button
          v-if="resolvedClassroomId"
          circle
          size="small"
          @click="openInNewWindow"
          title="在独立窗口中演播"
          class="!border-[var(--border-default)]"
        >
          <el-icon><Promotion /></el-icon>
        </el-button>

        <el-button
          circle
          size="small"
          @click="toggleFullscreen"
          :title="isFullscreen ? '退出全屏' : '全屏演播'"
          class="!border-[var(--border-default)]"
        >
          <el-icon><View /></el-icon>
        </el-button>

        <el-button
          circle
          size="small"
          @click="goBack"
          title="关闭微课"
          class="!border-[var(--border-default)]"
        >
          <el-icon><Close /></el-icon>
        </el-button>
      </div>
    </header>

    <!-- 主视口区域 -->
    <div class="flex-1 relative w-full h-full overflow-hidden bg-black/5 dark:bg-black/20">
      <!-- 1. 正在初始化数据态 -->
      <div
        v-if="loading"
        class="absolute inset-0 z-20 flex flex-col items-center justify-center p-8 space-y-4 bg-[var(--bg-primary)]"
      >
        <el-icon class="text-4xl text-[var(--color-primary)] reicon-spin"><Loading /></el-icon>
        <div class="text-center space-y-1">
          <p class="text-sm font-medium text-[var(--text-primary)]">正在加载 AI 互动微课...</p>
          <p class="text-xs text-[var(--text-muted)]">连接 OpenMAIC 引擎演播环境与剧本数据</p>
        </div>
      </div>

      <!-- 2. 错误/异常态 -->
      <div
        v-else-if="error || !resolvedClassroomId"
        class="absolute inset-0 z-20 flex flex-col items-center justify-center p-8 space-y-4 bg-[var(--bg-primary)]"
      >
        <div class="w-16 h-16 rounded-2xl bg-[var(--color-warning)]/10 flex items-center justify-center text-[var(--color-warning)] mb-1 shadow-sm">
          <el-icon class="text-3xl"><CircleCloseFilled /></el-icon>
        </div>
        <h2 class="text-base sm:text-lg font-semibold text-[var(--text-primary)]">未能载入互动微课</h2>
        <p class="text-xs sm:text-sm text-[var(--text-muted)] max-w-md text-center leading-relaxed">
          {{ error || '当前课程暂未生成互动微课，请前往课程详情页点击“生成课堂”。' }}
        </p>
        <div class="flex items-center gap-3 mt-4">
          <el-button type="primary" @click="goBack">返回课程空间</el-button>
          <el-button @click="initClassroom">重试连接</el-button>
        </div>
      </div>

      <!-- 3. OpenMAIC 高保真嵌入 iframe -->
      <template v-else>
        <!-- iframe 加载中的优雅骨架遮罩 -->
        <div
          v-if="!iframeReady"
          class="absolute inset-0 z-10 flex flex-col items-center justify-center p-8 space-y-3 bg-[var(--bg-primary)] transition-opacity duration-300 pointer-events-none"
        >
          <el-icon class="text-3xl text-[var(--color-primary)] reicon-spin"><Loading /></el-icon>
          <p class="text-xs text-[var(--text-muted)] animate-pulse">正在载入 OpenMAIC 画布与声学引擎...</p>
        </div>

        <iframe
          ref="engineIframe"
          :src="engineSrc"
          class="w-full h-full border-0 block"
          allow="autoplay; camera; microphone; display-capture; clipboard-read; clipboard-write; fullscreen"
          sandbox="allow-same-origin allow-scripts allow-popups allow-forms allow-downloads"
          @load="onIframeLoad"
        />
      </template>
    </div>

    <!-- 课堂设置抽屉/弹窗 -->
    <el-dialog
      v-model="settingsVisible"
      title="微课设置"
      width="500px"
      append-to-body
      class="classroom-settings-dialog"
    >
      <div class="space-y-5 py-1">
        <!-- 1. 演播控制 -->
        <div>
          <h3 class="text-xs font-semibold text-[var(--text-primary)] uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
            <el-icon><VideoPlay /></el-icon>
            演播与语音控制
          </h3>
          <div class="space-y-3.5 bg-[var(--bg-secondary)] p-3.5 rounded-xl border border-[var(--border-default)]">
            <!-- 语速倍速 -->
            <div class="flex items-center justify-between">
              <div>
                <div class="text-xs font-medium text-[var(--text-primary)]">播放倍速</div>
                <div class="text-[11px] text-[var(--text-muted)]">调节老师讲解与研讨发言节奏</div>
              </div>
              <el-radio-group
                v-model="playerConfig.speed"
                size="small"
                @change="onSpeedChange"
              >
                <el-radio-button :value="1">1.0x</el-radio-button>
                <el-radio-button :value="1.25">1.25x</el-radio-button>
                <el-radio-button :value="1.5">1.5x</el-radio-button>
                <el-radio-button :value="2">2.0x</el-radio-button>
              </el-radio-group>
            </div>

            <!-- 语音朗读音量 -->
            <div>
              <div class="flex items-center justify-between mb-1">
                <div class="text-xs font-medium text-[var(--text-primary)]">朗读音量</div>
                <div class="flex items-center gap-2">
                  <span class="text-xs font-mono text-[var(--text-muted)]">{{ volumePercent }}%</span>
                  <el-button
                    link
                    size="small"
                    @click="toggleMute"
                    :class="playerConfig.muted ? 'text-[var(--color-danger)]' : 'text-[var(--text-muted)]'"
                  >
                    {{ playerConfig.muted ? '取消静音' : '静音' }}
                  </el-button>
                </div>
              </div>
              <el-slider
                v-model="volumePercent"
                :min="0"
                :max="100"
                :step="5"
                :disabled="playerConfig.muted"
                @change="onVolumeChange"
              />
            </div>

            <!-- 自动连播 -->
            <div class="flex items-center justify-between pt-1 border-t border-[var(--border-default)]/60">
              <div>
                <div class="text-xs font-medium text-[var(--text-primary)]">自动连播下一幕</div>
                <div class="text-[11px] text-[var(--text-muted)]">当前小节讲解完毕后自动转入下一幕</div>
              </div>
              <el-switch
                v-model="playerConfig.autoPlay"
                @change="onAutoPlayChange"
              />
            </div>
          </div>
        </div>

        <!-- 2. 主模型与讨论引擎 -->
        <div>
          <h3 class="text-xs font-semibold text-[var(--text-primary)] uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
            <el-icon><Brain /></el-icon>
            主模型与讨论引擎
          </h3>
          <div class="bg-[var(--bg-secondary)] p-3.5 rounded-xl border border-[var(--border-default)] space-y-2.5">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span class="text-xs font-semibold text-[var(--text-primary)]">
                  {{ playerConfig.modelId || 'step-3.7-flash' }}
                </span>
              </div>
              <span class="text-[10px] px-2 py-0.5 rounded-full bg-[var(--color-success-light)] text-[var(--color-success)] font-medium border border-[var(--color-success)]/20">
                已接入 · 无感直通
              </span>
            </div>
            <p class="text-[11px] text-[var(--text-muted)] leading-relaxed">
              微课中的随堂提问与圆桌研讨已自动接入 Study Copilot 配置的主大模型，无需在微课内单独填写 API Key。
            </p>
            <div class="pt-2 border-t border-[var(--border-default)]/60 flex items-center justify-between">
              <span class="text-[11px] text-[var(--text-muted)]">如需更换系统主模型</span>
              <el-button
                size="small"
                type="primary"
                plain
                @click="goToModelConfig"
              >
                前往模型设置
              </el-button>
            </div>
          </div>
        </div>

        <!-- 3. 参会人设说明 -->
        <div>
          <h3 class="text-xs font-semibold text-[var(--text-primary)] uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
            <el-icon><User /></el-icon>
            微课参会人设
          </h3>
          <div class="grid grid-cols-3 gap-2">
            <div class="p-2 rounded-lg border border-[var(--border-default)] bg-[var(--surface-card)] text-center space-y-1">
              <div class="text-xs font-semibold text-[var(--text-primary)] flex items-center justify-center gap-1">
                <el-icon class="text-emerald-500"><GraduationCap /></el-icon>
                苏老师
              </div>
              <div class="text-[10px] text-[var(--text-muted)] leading-tight">主讲教师 · 课程串讲与白板推演</div>
            </div>
            <div class="p-2 rounded-lg border border-[var(--border-default)] bg-[var(--surface-card)] text-center space-y-1">
              <div class="text-xs font-semibold text-[var(--text-primary)] flex items-center justify-center gap-1">
                <el-icon class="text-sky-500"><Lightning /></el-icon>
                学霸同学
              </div>
              <div class="text-[10px] text-[var(--text-muted)] leading-tight">研讨分析 · 深度思辨与概念延伸</div>
            </div>
            <div class="p-2 rounded-lg border border-[var(--border-default)] bg-[var(--surface-card)] text-center space-y-1">
              <div class="text-xs font-semibold text-[var(--text-primary)] flex items-center justify-center gap-1">
                <el-icon class="text-amber-500"><User /></el-icon>
                求知同学
              </div>
              <div class="text-[10px] text-[var(--text-muted)] leading-tight">互动探索 · 积极提问与疑点追问</div>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useCourseStore } from '../stores/course'
import { useThemeStore } from '../stores/theme'
import { parseCourseDescription } from '../utils/course'
import {
  ArrowLeft,
  Close,
  Loading,
  CircleCloseFilled,
  Tickets,
  Document,
  Promotion,
  View,
  Setting,
  VideoPlay,
  Brain,
  GraduationCap,
  Lightning,
  User,
} from '../components/icons'

const route = useRoute()
const router = useRouter()
const courseStore = useCourseStore()

const themeStore = useThemeStore()
const playerContainer = ref<HTMLElement | null>(null)
const engineIframe = ref<HTMLIFrameElement | null>(null)

const loading = ref(true)
const iframeReady = ref(false)
const error = ref('')
const isFullscreen = ref(false)
const settingsVisible = ref(false)

const playerConfig = ref({
  speed: 1,
  volume: 1,
  muted: false,
  autoPlay: true,
  modelId: 'step-3.7-flash',
})

const volumePercent = computed({
  get: () => Math.round(playerConfig.value.volume * 100),
  set: (val: number) => {
    playerConfig.value.volume = val / 100
  },
})

const resolvedClassroomId = ref('')
const courseTitle = ref('AI 互动微课')
const sourceDocuments = ref<Array<{ id?: string; filename?: string; file_size?: number }>>([])

const courseId = computed(() => {
  if ((route.path || '').startsWith('/courses/')) {
    return (route.params?.id as string) || ''
  }
  return ''
})

const engineSrc = computed(() => {
  if (!resolvedClassroomId.value) return ''
  const theme = themeStore.isDark ? 'dark' : 'light'
  return `/classroom-engine/classroom/${resolvedClassroomId.value}?embedded=true&theme=${theme}`
})

// 监听宿主主题变化，跨 iframe 实时向 OpenMAIC 发送主题切换消息
watch(
  () => themeStore.isDark,
  (isDark) => {
    const theme = isDark ? 'dark' : 'light'
    if (engineIframe.value?.contentWindow) {
      engineIframe.value.contentWindow.postMessage({ type: 'SET_THEME', theme }, '*')
    }
  }
)

function formatSize(bytes?: number): string {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function onIframeLoad() {
  setTimeout(() => {
    iframeReady.value = true
    const theme = themeStore.isDark ? 'dark' : 'light'
    if (engineIframe.value?.contentWindow) {
      engineIframe.value.contentWindow.postMessage({ type: 'SET_THEME', theme }, '*')
    }
  }, 300)
}

function goBack() {
  if (courseId.value) {
    router.push(`/courses/${courseId.value}`)
  } else {
    router.back()
  }
}

function openInNewWindow() {
  if (resolvedClassroomId.value) {
    window.open(`/classroom-engine/classroom/${resolvedClassroomId.value}`, '_blank')
  }
}

function toggleFullscreen() {
  if (!playerContainer.value) return
  if (!document.fullscreenElement) {
    playerContainer.value.requestFullscreen().then(() => {
      isFullscreen.value = true
    }).catch(() => {})
  } else {
    document.exitFullscreen().then(() => {
      isFullscreen.value = false
    }).catch(() => {})
  }
}

function handleFullscreenChange() {
  isFullscreen.value = Boolean(document.fullscreenElement)
}

function sendConfigToIframe() {
  if (engineIframe.value?.contentWindow) {
    engineIframe.value.contentWindow.postMessage(
      {
        type: 'SET_CONFIG',
        speed: playerConfig.value.speed,
        volume: playerConfig.value.volume,
        muted: playerConfig.value.muted,
        autoPlay: playerConfig.value.autoPlay,
      },
      '*'
    )
  }
}

function onSpeedChange(val: any) {
  playerConfig.value.speed = Number(val)
  sendConfigToIframe()
}

function onVolumeChange() {
  sendConfigToIframe()
}

function toggleMute() {
  playerConfig.value.muted = !playerConfig.value.muted
  sendConfigToIframe()
}

function onAutoPlayChange() {
  sendConfigToIframe()
}

function goToModelConfig() {
  settingsVisible.value = false
  router.push('/config')
}

function handleWindowMessage(event: MessageEvent) {
  if (!event.data || typeof event.data !== 'object') return
  const { type } = event.data

  if (type === 'OPENMAIC_READY') {
    iframeReady.value = true
    if (event.data?.config) {
      const cfg = event.data.config
      if (typeof cfg.speed === 'number') playerConfig.value.speed = cfg.speed
      if (typeof cfg.volume === 'number') playerConfig.value.volume = cfg.volume
      if (typeof cfg.muted === 'boolean') playerConfig.value.muted = cfg.muted
      if (typeof cfg.autoPlay === 'boolean') playerConfig.value.autoPlay = cfg.autoPlay
      if (cfg.modelId) playerConfig.value.modelId = cfg.modelId
    }
  } else if (type === 'OPENMAIC_EXIT') {
    goBack()
  } else if (type === 'OPENMAIC_QUIZ_COMPLETED') {
    const results = event.data?.results || []
    const correct = results.filter((r: any) => r.isCorrect).length
    if (results.length > 0) {
      ElMessage.success(`随堂测验已完成！答对 ${correct}/${results.length} 题，结果已自动同步。`)
    } else {
      ElMessage.success('随堂测验已完成，结果已自动同步！')
    }
  }
}

async function initClassroom() {
  loading.value = true
  error.value = ''
  iframeReady.value = false

  try {
    const rawId = (route.params.id as string) || ''
    if (!rawId) {
      error.value = '未指定微课 ID'
      return
    }

    if ((route.path || '').startsWith('/courses/')) {
      const course = await courseStore.fetchCourse(rawId)
      if (!course) {
        error.value = '课程空间不存在或已被删除'
        return
      }
      courseTitle.value = course.name || 'AI 互动微课'

      try {
        const docs = await courseStore.fetchCourseDocuments(rawId)
        sourceDocuments.value = (docs || []).map(d => ({
          id: d.id,
          filename: d.filename,
          file_size: d.file_size,
        }))
      } catch {
        sourceDocuments.value = []
      }

      const parsed = parseCourseDescription(course.description)
      const targetCid = parsed.classroomId || ''
      if (!targetCid) {
        error.value = '当前课程尚未生成完整的 AI 互动微课，请前往课程详情页点击“生成课堂”。'
        return
      }
      resolvedClassroomId.value = targetCid
    } else {
      resolvedClassroomId.value = rawId
    }

    try {
      const resp = await fetch(`/classroom-engine/api/classroom?id=${resolvedClassroomId.value}`)
      if (resp.ok) {
        const data = await resp.json()
        const classroom = data?.data?.classroom || data?.classroom
        if (classroom?.stage?.name) {
          courseTitle.value = classroom.stage.name
        }
      }
    } catch {
      // 预检失败不阻断 iframe
    }
  } catch (err: any) {
    error.value = err?.response?.data?.detail || err?.message || '加载微课信息失败'
  } finally {
    loading.value = false
  }
}

watch(
  () => route.params.id,
  (newId) => {
    if (newId) initClassroom()
  }
)

onMounted(() => {
  initClassroom()
  window.addEventListener('message', handleWindowMessage)
  document.addEventListener('fullscreenchange', handleFullscreenChange)
})

onUnmounted(() => {
  window.removeEventListener('message', handleWindowMessage)
  document.removeEventListener('fullscreenchange', handleFullscreenChange)
})
</script>

<style scoped>
iframe {
  color-scheme: normal;
}
</style>
