<template>
  <div class="msg-enter space-y-3">
    <!-- Header: 多角色讨论主标题与状态栏 -->
    <div class="flex items-center justify-between pb-2 border-b border-[var(--border-light)]">
      <div class="flex items-center gap-2 min-w-0">
        <div class="w-6 h-6 rounded-md bg-[var(--color-primary)]/10 text-[var(--color-primary)] flex items-center justify-center shrink-0">
          <el-icon :size="15"><ChatDotSquare /></el-icon>
        </div>
        <span class="text-sm font-semibold text-[var(--text-primary)]">多角色讨论</span>
      </div>

      <div class="flex items-center gap-2 text-xs text-[var(--text-muted)] shrink-0">
        <span v-if="timelineTurns.length > 0">
          {{ timelineTurns.length }} 轮观点交锋
        </span>
        <div v-if="message.isStreaming" class="flex items-center gap-1 text-[var(--color-primary)] ml-1">
          <span class="thinking-dot"></span>
          <span class="thinking-dot" style="animation-delay: 0.15s"></span>
          <span class="thinking-dot" style="animation-delay: 0.3s"></span>
          <span class="text-xs ml-0.5">讨论中…</span>
        </div>
      </div>
    </div>

    <!-- 异常状态提示 -->
    <div
      v-if="errorMessage"
      class="p-3.5 rounded-xl border border-red-200 dark:border-red-900/50 bg-red-50/70 dark:bg-red-950/20 flex items-start gap-2.5 text-xs text-[var(--color-error)] animate-fade-in"
    >
      <el-icon :size="16" class="mt-0.5 shrink-0 text-red-500"><WarningFilled /></el-icon>
      <div class="leading-relaxed whitespace-pre-wrap flex-1">{{ errorMessage }}</div>
    </div>

    <!-- 研讨角色筹备发言等待状态 -->
    <div
      v-if="message.isStreaming && timelineTurns.length === 0 && !message.currentSpeaker && !errorMessage"
      class="card p-4 flex items-center gap-3 text-xs text-[var(--text-muted)] animate-pulse"
    >
      <el-icon :size="18" class="text-[var(--color-primary)]"><Brain /></el-icon>
      <span>研讨角色正在梳理思路，准备发言…</span>
    </div>

    <!-- 一级菜单：多角色研讨过程（总折叠容器，解决上下文过长痛点） -->
    <div
      v-if="timelineTurns.length > 0 || message.currentSpeaker"
      class="rounded-xl border border-[var(--border-light)] bg-[var(--bg-secondary)]/30 overflow-hidden transition-all shadow-xs"
    >
      <!-- 一级菜单控制顶栏 -->
      <div
        class="flex items-center justify-between px-3.5 py-2.5 bg-[var(--bg-secondary)]/80 hover:bg-[var(--bg-secondary)] cursor-pointer select-none transition-colors border-b border-[var(--border-light)]"
        @click="toggleProcessCollapse"
      >
        <div class="flex items-center gap-2 min-w-0">
          <el-icon
            :size="13"
            class="text-[var(--text-muted)] transition-transform duration-200 shrink-0"
            :class="{ 'rotate-90': isProcessExpanded }"
          >
            <ArrowRight />
          </el-icon>
          <span class="text-xs font-semibold text-[var(--text-primary)]">多角色研讨过程</span>
          <span v-if="message.isStreaming" class="flex items-center gap-1 text-[10px] text-[var(--color-primary)] ml-1">
            <span class="inline-block w-1.5 h-1.5 rounded-full bg-current animate-ping"></span>
            <span>实时推进中</span>
          </span>
        </div>

        <div class="flex items-center gap-2 text-[11px] text-[var(--text-muted)] shrink-0">
          <span>共 {{ totalRounds }} 轮交锋</span>
        </div>
      </div>

      <!-- 一级展开内容区域 -->
      <div v-show="isProcessExpanded" class="p-3 space-y-3">
        <!-- 活跃发言者实时动态状态栏 -->
        <div
          v-if="message.currentSpeaker"
          class="p-2.5 px-3.5 rounded-xl border border-[var(--color-primary)]/25 bg-[var(--color-primary)]/5 flex items-center gap-3 text-xs animate-fade-in"
        >
          <div
            class="w-6 h-6 rounded-full flex items-center justify-center text-xs shrink-0"
            :style="{
              backgroundColor: (message.currentSpeaker.color || '#3b82f6') + '25',
              color: message.currentSpeaker.color || 'var(--color-primary)'
            }"
          >
            <el-icon :size="13">
              <component :is="getPersonaIcon(message.currentSpeaker)" />
            </el-icon>
          </div>
          <div class="flex-1 min-w-0 flex items-center gap-2">
            <span class="font-semibold text-[var(--text-primary)]">{{ message.currentSpeaker.name }}</span>
            <span class="text-[var(--text-secondary)] truncate">{{ message.currentSpeaker.action || '正在阐述观点…' }}</span>
          </div>
          <div class="flex items-center gap-1 shrink-0 text-[var(--color-primary)]">
            <span class="thinking-dot"></span>
            <span class="thinking-dot" style="animation-delay: 0.15s"></span>
            <span class="thinking-dot" style="animation-delay: 0.3s"></span>
          </div>
        </div>

        <!-- 二级菜单列表：按轮次 (Rounds) 划分的折叠面板 -->
        <div class="space-y-2.5">
          <div
            v-for="round in groupedRounds"
            :key="round.turnNumber"
            class="rounded-lg border border-[var(--border-light)] bg-[var(--bg-primary)] overflow-hidden transition-all"
          >
            <!-- 二级菜单 Header：轮次折叠切换栏 -->
            <div
              class="flex items-center justify-between px-3 py-2 bg-[var(--bg-secondary)]/50 hover:bg-[var(--bg-secondary)] cursor-pointer select-none transition-colors border-b border-[var(--border-light)]"
              @click="toggleRoundCollapse(round.turnNumber)"
            >
              <div class="flex items-center gap-2 min-w-0">
                <el-icon
                  :size="12"
                  class="text-[var(--text-muted)] transition-transform duration-200 shrink-0"
                  :class="{ 'rotate-90': isRoundExpanded(round.turnNumber) }"
                >
                  <ArrowRight />
                </el-icon>
                <span class="text-xs font-semibold text-[var(--text-primary)]">
                  第 {{ round.turnNumber }} 轮{{ round.turnNumber > 1 ? ' · 深度互辩与交锋' : ' · 初始立论与破题' }}
                </span>
                <!-- 轮次内参会发言者徽章 -->
                <div class="flex items-center gap-1 overflow-hidden">
                  <span
                    v-for="sp in round.speakers"
                    :key="sp.name"
                    class="text-[10px] px-1.5 py-0.5 rounded font-medium truncate max-w-[80px]"
                    :style="{
                      backgroundColor: (sp.color || '#3b82f6') + '15',
                      color: sp.color || 'var(--color-primary)'
                    }"
                  >
                    {{ sp.name }}
                  </span>
                </div>
              </div>

              <div class="flex items-center gap-2 text-[10px] text-[var(--text-muted)] shrink-0">
                <span v-if="round.isStreaming" class="flex items-center gap-1 text-[var(--color-primary)] font-medium">
                  <span class="inline-block w-1.5 h-1.5 rounded-full bg-current animate-ping"></span>
                  <span>输出中…</span>
                </span>
                <span>{{ round.turns.length }} 条发言</span>
                <span class="text-[var(--color-primary)] font-medium">
                  {{ isRoundExpanded(round.turnNumber) ? '收起' : '展开' }}
                </span>
              </div>
            </div>

            <!-- 二级折叠容器内部：三级菜单——角色发言实际内容（实时逐字流式打字呈现） -->
            <div v-show="isRoundExpanded(round.turnNumber)" class="p-3 space-y-3 bg-[var(--bg-primary)]">
              <div
                v-for="turn in round.turns"
                :key="turn.id"
                class="flex gap-2.5 group"
              >
                <!-- 角色头像 -->
                <div
                  class="w-7 h-7 rounded-md border flex items-center justify-center shrink-0 mt-0.5 shadow-xs transition-colors"
                  :style="{
                    backgroundColor: (turn.color || '#3b82f6') + '15',
                    borderColor: (turn.color || '#3b82f6') + '33',
                    color: turn.color || 'var(--color-primary)'
                  }"
                >
                  <el-icon :size="15">
                    <component :is="getPersonaIcon(turn)" />
                  </el-icon>
                </div>

                <!-- 三级发言气泡卡片（支持发言正文折叠/展开） -->
                <div class="flex-1 min-w-0 card p-3 transition-all relative">
                  <!-- 三级卡片可点击顶栏：支持折叠/展开具体角色发言正文 -->
                  <div
                    class="flex items-center justify-between gap-2 cursor-pointer select-none"
                    :class="{ 'mb-1.5': isTurnExpanded(turn.id, turn.isStreaming) }"
                    @click="toggleTurnCollapse(turn.id)"
                  >
                    <div class="flex items-center gap-1.5 min-w-0">
                      <el-icon
                        :size="10"
                        class="text-[var(--text-muted)] transition-transform duration-200 shrink-0"
                        :class="{ 'rotate-90': isTurnExpanded(turn.id, turn.isStreaming) }"
                      >
                        <ArrowRight />
                      </el-icon>
                      <span class="text-xs font-semibold text-[var(--text-primary)]">{{ turn.persona }}</span>
                      <span
                        class="text-[9px] px-1.5 py-0.5 rounded font-medium"
                        :style="{
                          backgroundColor: (turn.color || '#3b82f6') + '15',
                          color: turn.color || 'var(--color-primary)'
                        }"
                      >
                        {{ round.turnNumber > 1 ? '互辩交锋' : '初始立论' }}
                      </span>
                    </div>

                    <div class="flex items-center gap-2 shrink-0">
                      <div v-if="turn.isStreaming" class="flex items-center gap-1 text-[9px] text-[var(--color-primary)]">
                        <span class="inline-block w-1.5 h-1.5 rounded-full bg-current animate-ping"></span>
                        <span>发言中…</span>
                      </div>
                      <span class="text-[10px] text-[var(--text-muted)] hover:text-[var(--color-primary)] transition-colors">
                        {{ isTurnExpanded(turn.id, turn.isStreaming) ? '收起' : '展开' }}
                      </span>
                      <!-- 一键复制单条发言 -->
                      <button
                        class="opacity-0 group-hover:opacity-100 text-[10px] text-[var(--text-muted)] hover:text-[var(--color-primary)] transition-opacity p-0.5 rounded hover:bg-[var(--bg-secondary)]"
                        :title="copiedTurnId === turn.id ? '已复制' : '复制此条发言'"
                        @click.stop="copyTurnContent(turn.content, turn.id)"
                      >
                        <el-icon :size="12">
                          <Check v-if="copiedTurnId === turn.id" class="text-emerald-500" />
                          <DocumentCopy v-else />
                        </el-icon>
                      </button>
                    </div>
                  </div>

                  <!-- 折叠时的单行文本缩略预览 -->
                  <div
                    v-if="!isTurnExpanded(turn.id, turn.isStreaming) && turn.content"
                    class="text-[11px] text-[var(--text-muted)] truncate mt-0.5 cursor-pointer"
                    @click="toggleTurnCollapse(turn.id)"
                  >
                    {{ turn.content.replace(/[#*`\n]/g, ' ').trim() }}
                  </div>

                  <!-- 三级发言正文：流式逐字 Markdown 渲染 + 呼吸光标 -->
                  <div v-show="isTurnExpanded(turn.id, turn.isStreaming)">
                    <div
                      class="text-xs text-[var(--text-secondary)] leading-relaxed whitespace-pre-wrap prose prose-sm max-w-none"
                      v-html="renderMarkdown(turn.content)"
                    ></div>
                    <span
                      v-if="turn.isStreaming"
                      class="inline-block w-1.5 h-3.5 bg-[var(--color-primary)] ml-0.5 animate-pulse align-middle"
                    ></span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 主持人讨论总结卡片（独立沉淀于一级讨论过程下方，即使折叠研讨过程也醒目展示结论） -->
    <div
      v-if="summaryContent || message.summaryStreaming"
      class="mt-3 p-4 rounded-xl border border-emerald-500/25 bg-emerald-50/40 dark:bg-emerald-950/20 space-y-2.5 transition-all animate-fade-in"
    >
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
          <div class="w-6 h-6 rounded-md bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center">
            <el-icon :size="14"><ChatDotSquare /></el-icon>
          </div>
          <span>讨论总结</span>
          <span class="text-[10px] font-normal text-[var(--text-muted)] bg-emerald-500/10 px-1.5 py-0.5 rounded">主持人 · 核心共识与实践建议</span>
        </div>
        <div v-if="message.summaryStreaming" class="flex items-center gap-1 text-[10px] text-emerald-600 dark:text-emerald-400">
          <span class="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping"></span>
          <span>归纳中…</span>
        </div>
      </div>
      <div
        v-if="summaryContent"
        class="text-sm text-[var(--text-secondary)] leading-relaxed whitespace-pre-wrap prose prose-sm max-w-none"
        v-html="renderMarkdown(summaryContent)"
      ></div>
      <span
        v-if="message.summaryStreaming"
        class="inline-block w-1.5 h-3.5 bg-emerald-500 ml-0.5 animate-pulse align-middle"
      ></span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import type { ChatStreamMessage, DiscussionTurn } from '@/stores/chat'
import { useMarkdown } from '@/composables/useMarkdown'
import {
  ChatDotSquare,
  User,
  GraduationCap,
  ChatLineRound,
  EditPen,
  Brain,
  Lightning,
  MagicStick,
  Reading,
  Search,
  TrendCharts,
  Promotion,
  Setting,
  Clock,
  Tickets,
  Document,
  WarningFilled,
  ArrowRight,
  DocumentCopy,
  Check
} from '@/components/icons'

const props = defineProps<{
  message: ChatStreamMessage
}>()

const { renderMarkdown } = useMarkdown()

/** 一级菜单：多角色研讨过程折叠状态（生成中默认展开，让流式打字可见；也可随时手动收起） */
const isProcessExpanded = ref<boolean>(true)

function toggleProcessCollapse() {
  isProcessExpanded.value = !isProcessExpanded.value
}

/** 复制单条发言反馈状态 */
const copiedTurnId = ref<string | null>(null)
let copyTimer: ReturnType<typeof setTimeout> | null = null

function copyTurnContent(content: string, id: string) {
  if (!content) return
  try {
    navigator.clipboard.writeText(content)
    copiedTurnId.value = id
    if (copyTimer) clearTimeout(copyTimer)
    copyTimer = setTimeout(() => {
      copiedTurnId.value = null
    }, 2000)
  } catch {
    // 忽略剪切板权限异常
  }
}

/** 规范化全量发言列表 */
const timelineTurns = computed<DiscussionTurn[]>(() => {
  if (props.message.discussionTurns && props.message.discussionTurns.length > 0) {
    return props.message.discussionTurns
  }
  // 兼容从旧版 personas 结构转换
  if (props.message.personas && props.message.personas.length > 0) {
    return props.message.personas.map((p, idx) => ({
      id: `p-${idx}`,
      persona: p.name,
      avatar: p.avatar,
      color: p.color,
      content: p.content,
      turn: 1,
      isStreaming: false,
    }))
  }
  return []
})

/** 二级菜单分组接口 */
interface RoundGroup {
  turnNumber: number
  speakers: Array<{ name: string; avatar: string; color?: string }>
  turns: DiscussionTurn[]
  isStreaming: boolean
}

/** 二级菜单：按轮次分组发言 */
const groupedRounds = computed<RoundGroup[]>(() => {
  const turns = timelineTurns.value
  if (!turns.length) return []

  const groupsMap = new Map<number, DiscussionTurn[]>()
  for (const t of turns) {
    const roundNum = t.turn || 1
    if (!groupsMap.has(roundNum)) {
      groupsMap.set(roundNum, [])
    }
    groupsMap.get(roundNum)!.push(t)
  }

  const result: RoundGroup[] = []
  for (const [roundNum, roundTurns] of groupsMap.entries()) {
    const speakerMap = new Map<string, { name: string; avatar: string; color?: string }>()
    for (const t of roundTurns) {
      if (!speakerMap.has(t.persona)) {
        speakerMap.set(t.persona, {
          name: t.persona,
          avatar: t.avatar,
          color: t.color,
        })
      }
    }
    result.push({
      turnNumber: roundNum,
      speakers: Array.from(speakerMap.values()),
      turns: roundTurns,
      isStreaming: roundTurns.some(t => t.isStreaming),
    })
  }

  return result.sort((a, b) => a.turnNumber - b.turnNumber)
})

/** 研讨总轮数 */
const totalRounds = computed(() => {
  if (groupedRounds.value.length > 0) {
    return groupedRounds.value[groupedRounds.value.length - 1].turnNumber
  }
  return timelineTurns.value.length ? 1 : 0
})

/** 二级菜单各轮次的展开/折叠状态表 */
const expandedRounds = reactive<Record<number, boolean>>({})

function isRoundExpanded(roundNum: number): boolean {
  if (expandedRounds[roundNum] !== undefined) {
    return expandedRounds[roundNum]
  }
  // 默认规则：当前正在流式输出的轮次自动展开，最新轮次默认展开
  const round = groupedRounds.value.find(r => r.turnNumber === roundNum)
  if (round && round.isStreaming) return true
  // 默认全部轮次展开，方便用户纵览，用户可随时单轮收起
  return true
}

function toggleRoundCollapse(roundNum: number) {
  const current = isRoundExpanded(roundNum)
  expandedRounds[roundNum] = !current
}

/** 三级菜单：各角色单条发言正文的展开/折叠状态表 */
const expandedTurns = reactive<Record<string, boolean>>({})

function isTurnExpanded(turnId: string, isStreaming?: boolean): boolean {
  // 流式输出中的发言保持展开，字字可见
  if (isStreaming) return true
  if (expandedTurns[turnId] !== undefined) {
    return expandedTurns[turnId]
  }
  // 默认全部展开，方便用户直接查阅，亦可随时单独收起
  return true
}

function toggleTurnCollapse(turnId: string) {
  const current = isTurnExpanded(turnId)
  expandedTurns[turnId] = !current
}

// 监听流式状态：当有新轮次正在流式生成时，确保一级容器和该轮次自动处于展开状态
watch(
  () => props.message.isStreaming,
  (streaming) => {
    if (streaming) {
      isProcessExpanded.value = true
    }
  }
)

const summaryContent = computed(() => {
  if (props.message.summary) return props.message.summary
  if (props.message.content && props.message.content.includes('**讨论总结**\n\n')) {
    const parts = props.message.content.split('**讨论总结**\n\n')
    return parts[parts.length - 1].trim()
  }
  return ''
})

const errorMessage = computed(() => {
  if (props.message.error) return props.message.error
  const c = props.message.content || ''
  if (
    c.includes('讨论失败') ||
    c.includes('讨论生成失败') ||
    c.includes('讨论服务暂时不可用') ||
    c.startsWith('HTTP ') ||
    c.startsWith('Error:')
  ) {
    const parts = c.split('\n\n---\n\n')
    const errPart = parts.find(
      p => p.includes('失败') || p.includes('不可用') || p.startsWith('HTTP ') || p.startsWith('Error:')
    )
    return errPart || (!timelineTurns.value.length ? c : '')
  }
  return ''
})

const personaIcons: Record<string, any> = {
  User,
  GraduationCap,
  ChatLineRound,
  EditPen,
  Brain,
  Lightning,
  MagicStick,
  Reading,
  Search,
  TrendCharts,
  Promotion,
  Setting,
  Clock,
  Tickets,
  Document,
  ChatDotSquare,
  WarningFilled
}

function getPersonaIcon(persona: { name?: string; avatar?: string; role?: string; persona?: string }): any {
  if (persona.avatar && personaIcons[persona.avatar]) {
    return personaIcons[persona.avatar]
  }
  const role = persona.role?.toLowerCase() || ''
  const name = persona.persona || persona.name || ''

  if (role === 'teacher' || name.includes('老师') || name.includes('讲师')) return User
  if (role === 'thinker' || name.includes('学霸') || name.includes('思考')) return GraduationCap
  if (role === 'curious' || name.includes('同学') || name.includes('求知') || name.includes('提问')) return ChatLineRound
  if (role === 'notetaker' || name.includes('助手') || name.includes('笔记') || name.includes('归纳')) return EditPen
  if (role === 'host' || name.includes('主持')) return ChatDotSquare
  return User
}
</script>
