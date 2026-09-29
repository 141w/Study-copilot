<template>
  <div class="flex" :style="containerHeightStyle">
    <!-- Chat Area -->
    <div class="flex-1 flex flex-col" @mouseenter="mouseInChat = true" @mouseleave="mouseInChat = false">
      <!-- Top Bar
           底色取 --bg-secondary（亮 #e9e9f2 / 暗 #0a0a0a）：
           比纯白 --surface-card 暗一档，不再是压在 #f0f0fa 页面上的"高光横档"；
           又比页面底色深一档，让工具栏与消息区保留可辨的分层。
           与 AnalysisView / WikiView 的顶部底色取值一致。 -->
      <div class="border-b border-[var(--border-default)] px-4 sm:px-6 py-2.5 bg-[var(--bg-secondary)] flex items-center justify-between gap-3 overflow-x-auto">
        <div class="flex items-center gap-3 min-w-0 shrink">
          <h1 class="text-lg sm:text-xl font-semibold text-[var(--text-primary)] shrink-0">AI 问答</h1>
          <span
            v-if="chatStore.currentSession"
            class="text-xs sm:text-sm text-[var(--text-muted)] truncate max-w-[140px] sm:max-w-[220px]"
            :title="chatStore.currentSessionTitle"
          >
            {{ chatStore.currentSessionTitle }}
          </span>
        </div>

        <div class="flex items-center gap-2 shrink-0">
          <el-button type="primary" size="small" :icon="Plus" class="!px-2.5" @click="newChat">新建对话</el-button>

          <el-tooltip content="导出当前会话为 Markdown" placement="bottom">
            <el-button
              size="small"
              :icon="Download"
              :disabled="chatStore.messages.length === 0"
              class="!px-2 sm:!px-2.5"
              @click="exportChat"
            >
              <span class="hidden xl:inline ml-1">导出</span>
            </el-button>
          </el-tooltip>

          <!-- 模式切换：问答 / 讨论 -->
          <div class="flex items-center gap-1.5 text-sm border-l border-[var(--border-default)] pl-2.5 ml-0.5">
            <el-radio-group v-model="chatMode" size="small">
              <el-radio-button label="qa">问答</el-radio-button>
              <el-radio-button label="discuss">讨论</el-radio-button>
            </el-radio-group>
          </div>

          <!-- 问答模式子项：快速问答 / 深度研究 (ReAct) -->
          <Transition name="fade">
            <div v-if="chatMode === 'qa'" class="flex items-center gap-1.5 shrink-0">
              <el-radio-group v-model="researchMode" size="small" class="agent-mode-radios">
                <el-radio-button label="fast">
                  <span class="flex items-center gap-1">
                    <el-icon :size="12"><Lightning /></el-icon>
                    <span>快速</span>
                  </span>
                </el-radio-button>
                <el-radio-button label="deep_research">
                  <span class="flex items-center gap-1">
                    <el-icon :size="12"><Brain /></el-icon>
                    <span>深度研究</span>
                  </span>
                </el-radio-button>
              </el-radio-group>
            </div>
          </Transition>

          <!-- 讨论模式树形下拉配置框（整合讨论角色、上下文模式、研讨深度，节约横向空间） -->
          <Transition name="fade">
            <div v-if="chatMode === 'discuss'" class="flex items-center gap-1.5 shrink-0">
              <el-tree-select
                v-model="treeSelectValues"
                :data="discussTreeData"
                node-key="value"
                :props="{ label: 'label', children: 'children', disabled: 'disabled' }"
                multiple
                show-checkbox
                check-strictly
                check-on-click-node
                default-expand-all
                :indent="0"
                :fit-input-width="false"
                placement="bottom-end"
                popper-class="discuss-tree-popper"
                size="small"
                class="discuss-tree-select !text-xs"
                @change="onDiscussTreeChange"
              >
                <template #prefix>
                  <span class="text-xs text-[var(--text-primary)] font-medium select-none pl-0.5">讨论配置</span>
                </template>
                <template #default="{ data }">
                  <el-tooltip
                    :content="data.description"
                    :disabled="!data.description"
                    placement="left"
                    :show-after="200"
                    :enterable="false"
                  >
                    <span class="flex items-center gap-1.5 py-0.5 text-xs w-full">
                      <el-icon :size="13" class="shrink-0" :style="{ color: data.color || 'var(--text-secondary)' }">
                        <component :is="data.icon || User" />
                      </el-icon>
                      <span class="font-medium text-[var(--text-primary)] shrink-0">{{ data.label }}</span>
                      <span
                        v-if="data.isCustom"
                        class="ml-auto text-[9px] px-1 py-0.2 rounded font-medium"
                        :style="{ color: data.color || '#6366f1', backgroundColor: (data.color || '#6366f1') + '15' }"
                      >
                        自定义
                      </span>
                    </span>
                  </el-tooltip>
                </template>
              </el-tree-select>

              <!-- 管理研讨角色按钮 -->
              <el-tooltip content="管理研讨角色 (自定义角色)" placement="bottom">
                <el-button
                  size="small"
                  circle
                  aria-label="管理研讨角色"
                  class="persona-manage-btn"
                  @click="showPersonaDialog = true"
                >
                  <el-icon><User /></el-icon>
                </el-button>
              </el-tooltip>
            </div>
          </Transition>

          <div class="h-4 w-[1px] bg-[var(--border-default)] mx-0.5"></div>

          <!-- 历史记录（SVG 图标按钮） -->
          <el-tooltip :content="showHistory ? '隐藏历史记录' : '查看历史记录'" placement="bottom">
            <el-button
              size="small"
              :type="showHistory ? 'primary' : 'default'"
              circle
              aria-label="历史记录"
              @click="showHistory = !showHistory"
            >
              <el-icon><Clock /></el-icon>
            </el-button>
          </el-tooltip>

          <!-- 模型配置（SVG 图标按钮） -->
          <el-tooltip content="模型配置" placement="bottom">
            <router-link to="/model-config" class="inline-flex">
              <el-button size="small" circle aria-label="模型配置">
                <el-icon><Setting /></el-icon>
              </el-button>
            </router-link>
          </el-tooltip>
        </div>
      </div>

      <!-- Messages Area -->
      <div class="flex-1 min-h-0 overflow-hidden relative">
        <!-- 固定在视口右侧的定位轨，不随对话滚动 -->
        <ProximitySidebar
          v-if="proximitySections.length"
          :sections="proximitySections"
          :active-offset="0.4"
          @navigate="onProximityNavigate"
        />
        <div ref="messagesRef" class="h-full overflow-y-auto">
        <div v-if="chatStore.messages.length === 0" class="max-w-2xl mx-auto text-center py-16">
          <CopilotBotAvatar class="bot-avatar-flip" :size="120" :mood="avatarMood" :expression="avatarExpr" />
          <h2 class="text-2xl font-semibold text-[var(--text-primary)] mb-2">你好，我是 Study Copilot</h2>
          <p class="text-[var(--text-muted)] mb-6">基于你的文档知识库，我可以回答你的问题</p>
          <!-- P5-3：快捷入口可点（原为纯文字胶囊），每项带图标 + 动词-名词 -->
          <div class="grid grid-cols-1 sm:grid-cols-3 gap-2 max-w-xl mx-auto text-left">
            <router-link
              v-for="q in quickStarts"
              :key="q.to"
              :to="q.to"
              class="flex items-center gap-2.5 px-3.5 py-3 bg-[var(--surface-card)] border border-[var(--border-default)] rounded-lg hover:border-[var(--color-primary)] hover:shadow-sm transition-all group"
            >
              <el-icon class="w-[18px] h-[18px] flex-shrink-0" :class="q.iconClass"><component :is="q.icon" /></el-icon>
              <span class="text-sm text-[var(--text-secondary)] group-hover:text-[var(--text-primary)] transition-colors">{{ q.label }}</span>
            </router-link>
          </div>
          <!-- P0-A 起始问题 -->
          <div
            v-if="!startersDismissed && (chatStore.starterSuggestions.length || chatStore.starterSuggestionsLoading || chatStore.starterSuggestionsError)"
            class="mt-8 max-w-xl mx-auto"
            data-test="starter-suggestions"
          >
            <div class="flex items-center justify-center gap-2 mb-3">
              <span class="text-xs text-[var(--text-muted)]">
                {{ chatStore.starterSuggestionsLoading ? '生成引导问题中…' : '试试这样开始' }}
              </span>
              <button
                v-if="!chatStore.starterSuggestionsLoading"
                type="button"
                class="text-[11px] text-[var(--text-muted)] hover:text-[var(--text-secondary)] underline cursor-pointer"
                data-test="dismiss-starters"
                @click="dismissStarters"
              >
                不再显示
              </button>
            </div>
            <!-- F9：失败可见重试，不整块静默消失 -->
            <div
              v-if="chatStore.starterSuggestionsError && !chatStore.starterSuggestionsLoading"
              class="text-center text-xs text-[var(--text-muted)]"
              data-test="starter-retry"
            >
              暂时没想到合适的问题，
              <button
                type="button"
                class="underline text-[var(--color-primary)] cursor-pointer"
                data-test="starter-retry-btn"
                @click="void chatStore.loadStarterSuggestions(selectedDocs)"
              >点这里重试</button>
            </div>
            <div v-else class="flex flex-wrap justify-center gap-2">
              <button
                v-for="(s, i) in chatStore.starterSuggestions"
                :key="i"
                type="button"
                class="px-3 py-1.5 rounded-full border border-[var(--border-default)] text-sm text-[var(--text-secondary)] hover:border-[var(--color-primary)] hover:text-[var(--color-primary)] hover:bg-[var(--color-primary)]/5 transition-colors cursor-pointer"
                :data-test="`starter-chip-${i}`"
                @click="handleSend(s)"
              >
                {{ s }}
              </button>
            </div>
          </div>
        </div>

        <div v-else class="max-w-3xl mx-auto px-4 py-6 space-y-6">
          <!-- P7：assistant 尚未响应时（仅 user 消息），球暂驻顶部（FLIP 落点） -->
          <div v-if="lastAssistantIdx === -1" class="flex items-start gap-3 sm:gap-4">
            <div class="flex-shrink-0 w-11 flex justify-center">
              <CopilotBotAvatar class="bot-avatar-flip" :size="44" :mood="avatarMood" :expression="avatarExpr" />
            </div>
          </div>

          <template v-for="(msg, idx) in chatStore.messages" :key="idx">
            <!-- Discussion mode -->
            <div
              v-if="msg.role === 'discussion'"
              :id="`msg-${msg.id}`"
              :data-msg-id="String(msg.id)"
              data-msg-role="discussion"
            >
              <ChatDiscussionItem
                :message="msg"
              />
            </div>

            <!-- Regular Assistant / User message -->
            <div
              v-else
              :id="`msg-${msg.id}`"
              :data-msg-id="String(msg.id)"
              :data-msg-role="msg.role"
            >
              <ChatMessageItem
                :message="msg"
                :rendered-markdown="renderMarkdown(msg.content, msg.isStreaming)"
                :rendered-reasoning="msg.reasoning ? renderMarkdown(msg.reasoning, false) : undefined"
                :show-avatar="idx === lastAssistantIdx"
                :is-latest-assistant="msg === chatStore.messages[chatStore.messages.length - 1]"
                :avatar-mood="avatarMood"
                :avatar-expr="avatarExpr"
                :is-copied="copiedMsgId === msg.id"
                @copy="copyMessage"
                @scroll-to-source="scrollToSource"
                @ask="handleSend"
              />
            </div>
          </template>
        </div>
        </div><!-- /messagesRef -->
      </div><!-- /Messages Area -->

      <!-- Input Area -->
      <div class="border-t border-[var(--border-default)] bg-[var(--bg-primary)]/80 backdrop-blur-md">
        <div class="max-w-3xl mx-auto px-4 pt-2.5 pb-4 sm:pt-3 sm:pb-5">
          <ChatInput
            @send="handleSend"
            @stop="handleStop"
            :loading="chatStore.isStreaming"
            :scope-chips="scopeChips"
            :attachments="chatAttachments"
            @remove-scope="removeScope"
            @add-scope="addScope"
            @add-attachments="addChatAttachments"
            @remove-attachment="removeChatAttachment"
            placeholder="输入您的问题..."
          />
        </div>
      </div>
    </div>

    <!-- History Sidebar -->
    <ChatHistoryPanel
      :visible="showHistory"
      @close="showHistory = false"
      @loaded="onSessionLoaded"
      @deleted="onSessionDeleted"
    />

    <!-- 自定义角色管理弹窗 -->
    <PersonaManageDialog
      v-model="showPersonaDialog"
      @updated="onPersonaUpdated"
    />
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'ChatView' })

import { computed, ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import api from '../services/api'
import { useChatStore } from '../stores/chat'
import { withBase } from '../services/base'
import type { ChatStreamMessage } from '../stores/chat'
import type { BotMood } from '../components/CopilotBotAvatar.vue'
import type { ExpressionId } from '../bot/expressions'
import { useDocumentStore } from '../stores/document'
import { useCourseStore } from '../stores/course'
import ChatInput from '../components/chat/ChatInput.vue'
import ChatHistoryPanel from '../components/chat/ChatHistoryPanel.vue'
import ChatMessageItem from '../components/chat/ChatMessageItem.vue'
import ChatDiscussionItem from '../components/chat/ChatDiscussionItem.vue'
import ProximitySidebar from '../components/chat/ProximitySidebar.vue'
import PersonaManageDialog from '../components/chat/PersonaManageDialog.vue'
import type { ChatAttachmentItem } from '../components/chat/ChatAttachments.vue'
import { useVisualViewport } from '../composables/useVisualViewport'
import { buildChatMarkdown, downloadChatMarkdown } from '../composables/useChatExport'
import { useMarkdown } from '../composables/useMarkdown'
import {
  prepareCitationMarkdown,
  finalizeCitationHtml,
  hideIncompleteCitationTail,
} from '@/utils/citationMarkdown'
import { useReducedMotion } from '../composables/useReducedMotion'
import gsap from 'gsap'
import CopilotBotAvatar from '../components/CopilotBotAvatar.vue'
import { useUserPrefs } from '@/composables/useUserPrefs'
import {
  Plus,
  Download,
  Clock,
  Upload,
  Document,
  DocumentChecked,
  Setting,
  Search,
  User,
  ChatLineRound,
  EditPen,
  GraduationCap,
  Lightning,
  Brain,
  TrendCharts
} from '@/components/icons'

const { prefs } = useUserPrefs()
const { containerHeightStyle } = useVisualViewport()
const chatStore = useChatStore()
const documentStore = useDocumentStore()
const courseStore = useCourseStore()
const selectedDocs = ref<string[]>([])

const scopeChips = computed(() =>
  selectedDocs.value.map(id => {
    const doc = documentStore.documents?.find(d => d.id === id)
    return {
      key: `doc:${id}`,
      kind: 'doc' as const,
      id,
      label: doc?.filename || id,
    }
  })
)

function removeScope(chip: { kind: string; id: string }): void {
  if (chip.kind === 'doc') {
    selectedDocs.value = selectedDocs.value.filter(x => x !== chip.id)
  }
}

async function addScope(chip: { kind: string; id: string }): Promise<void> {
  if (chip.kind === 'doc' && !selectedDocs.value.includes(chip.id)) {
    selectedDocs.value = [...selectedDocs.value, chip.id]
  }
  // 课程维度：选中课程下 ready 文档一并纳入范围
  if (chip.kind === 'course') {
    try {
      const docs = await courseStore.fetchCourseDocuments(chip.id)
      const courseDocs = (docs || []).filter(d => d.status === 'ready').map(d => d.id)
      const merged = new Set([...selectedDocs.value, ...courseDocs])
      selectedDocs.value = [...merged]
    } catch {
      // 降级使用 documentStore 关联过滤
      const courseDocs = (documentStore.documents || [])
        .filter(d => (d as any).course_space_id === chip.id && d.status === 'ready')
        .map(d => d.id)
      const merged = new Set([...selectedDocs.value, ...courseDocs])
      selectedDocs.value = [...merged]
    }
  }
}
const showHistory = ref(false)
const showPersonaDialog = ref(false)
const botMood = ref<BotMood>('idle')
const messagesRef = ref<HTMLElement | null>(null)
const route = useRoute()
const chatMode = ref<'qa' | 'discuss'>('qa')
const researchMode = ref<'fast' | 'deep_research'>('fast')
// 讨论上下文模式（rag_snippets=检索片段 / full_docs=全文打包）
const discussContextMode = ref<'rag_snippets' | 'full_docs'>('rag_snippets')
const discussMaxTurns = ref<number>(2)

// ── Proximity sidebar：消息快速定位（rare-ui 横向短划线轨） ─────────────
const proximitySections = computed(() => {
  return chatStore.messages.map((m: any) => {
    const raw = String(m.content || m.summary || '')
    const preview = raw.replace(/\s+/g, ' ').trim().slice(0, 120) || '（空消息）'
    const role =
      m.role === 'user' ? '我' : m.role === 'discussion' ? '研讨' : 'Copilot'
    const kind =
      m.role === 'discussion'
        ? ('title' as const)
        : m.role === 'user'
          ? ('section' as const)
          : ('body' as const)
    return {
      id: `msg-${m.id}`,
      label: `${role}：${preview}`,
      preview,
      role,
      kind,
    }
  })
})

function onProximityNavigate(_id: string): void {
  // 组件内部已 scrollIntoView；此处保留 hook 供后续埋点
}

// AI 研讨多 Agent 讨论角色库
interface AvailablePersona {
  id?: string
  role: string
  name: string
  avatar?: string
  color?: string
  system_message?: string
  is_custom?: boolean
}
const availablePersonas = ref<AvailablePersona[]>([
  { role: 'teacher', name: '苏老师', avatar: 'User', color: '#3b82f6' },
  { role: 'thinker', name: '学霸', avatar: 'GraduationCap', color: '#10b981' },
  { role: 'curious', name: '求知同学', avatar: 'ChatLineRound', color: '#f59e0b' },
  { role: 'notetaker', name: '归纳助手', avatar: 'EditPen', color: '#8b5cf6' },
])
const selectedPersonas = ref<string[]>(['thinker', 'curious'])

const personaIconMap: Record<string, any> = {
  teacher: User,
  thinker: GraduationCap,
  curious: ChatLineRound,
  notetaker: EditPen,
  User,
  GraduationCap,
  ChatLineRound,
  EditPen,
  Brain,
  Lightning,
  TrendCharts
}

const personaDescMap: Record<string, string> = {
  thinker: '深入推导',
  curious: '提问质疑',
  teacher: '体系讲解',
  notetaker: '要点归纳',
}

// 讨论树形选项配置（把多按钮整合为一棵层级树，使用 SVG 图标代替 Emoji）
interface DiscussTreeNode {
  value: string
  label: string
  icon?: any
  avatar?: string
  color?: string
  description?: string
  disabled?: boolean
  isCustom?: boolean
  children?: DiscussTreeNode[]
}

const discussTreeData = computed<DiscussTreeNode[]>(() => [
  {
    value: 'group_personas',
    label: '讨论角色',
    icon: User,
    disabled: true,
    children: [
      ...availablePersonas.value.map(p => ({
        value: `persona_${p.role}`,
        label: p.name,
        avatar: p.avatar,
        color: p.color,
        icon: (p.avatar && personaIconMap[p.avatar]) || personaIconMap[p.role] || User,
        description: p.system_message
          ? (p.system_message.length > 30 ? p.system_message.slice(0, 30) + '...' : p.system_message)
          : (personaDescMap[p.role] || '参与研讨'),
        isCustom: !!p.is_custom
      })),
      {
        value: 'action_manage_personas',
        label: '管理/新建角色...',
        icon: Plus,
        description: '配置与创建专属研讨角色'
      }
    ]
  },
  {
    value: 'group_context',
    label: '参考上下文',
    icon: Document,
    disabled: true,
    children: [
      {
        value: 'context_rag_snippets',
        label: '检索片段',
        icon: Search,
        description: '语义检索'
      },
      {
        value: 'context_full_docs',
        label: '完整全文',
        icon: Document,
        description: '文档全文'
      }
    ]
  },
  {
    value: 'group_depth',
    label: '研讨深度',
    icon: TrendCharts,
    disabled: true,
    children: [
      {
        value: 'depth_standard',
        label: '标准研讨',
        icon: Lightning,
        description: '2 轮研讨'
      },
      {
        value: 'depth_deep',
        label: '深度辩论',
        icon: Brain,
        description: '3 轮辩论'
      }
    ]
  }
])

const treeSelectValues = ref<string[]>([
  'persona_thinker',
  'persona_curious',
  'context_rag_snippets',
  'depth_standard'
])

function onDiscussTreeChange(vals: string[]): void {
  let updated = [...vals]

  // 0. 快捷动作：管理/新建角色
  if (updated.includes('action_manage_personas')) {
    updated = updated.filter(v => v !== 'action_manage_personas')
    treeSelectValues.value = updated
    showPersonaDialog.value = true
    return
  }

  // 1. 上下文模式 (单选互斥)
  const contextKeys = updated.filter(v => v.startsWith('context_'))
  if (contextKeys.length > 1) {
    const previousContext = discussContextMode.value === 'full_docs' ? 'context_full_docs' : 'context_rag_snippets'
    const newContext = contextKeys.find(k => k !== previousContext) || contextKeys[contextKeys.length - 1]
    updated = updated.filter(v => !v.startsWith('context_') || v === newContext)
  } else if (contextKeys.length === 0) {
    updated.push('context_rag_snippets')
  }

  // 2. 研讨深度 (单选互斥)
  const depthKeys = updated.filter(v => v.startsWith('depth_'))
  if (depthKeys.length > 1) {
    const previousDepth = discussMaxTurns.value === 3 ? 'depth_deep' : 'depth_standard'
    const newDepth = depthKeys.find(k => k !== previousDepth) || depthKeys[depthKeys.length - 1]
    updated = updated.filter(v => !v.startsWith('depth_') || v === newDepth)
  } else if (depthKeys.length === 0) {
    updated.push('depth_standard')
  }

  // 3. 角色选择 (至少保留 1 个角色)
  const personaKeys = updated.filter(v => v.startsWith('persona_'))
  if (personaKeys.length === 0) {
    updated.push('persona_thinker')
  }

  treeSelectValues.value = updated

  // 同步到业务状态
  selectedPersonas.value = updated
    .filter(v => v.startsWith('persona_'))
    .map(v => v.replace('persona_', ''))

  discussContextMode.value = updated.includes('context_full_docs') ? 'full_docs' : 'rag_snippets'
  discussMaxTurns.value = updated.includes('depth_deep') ? 3 : 2
}

const loadPersonas = async () => {
  try {
    const { data } = await api.get('/chat/personas')
    if (Array.isArray(data?.personas) && data.personas.length > 0) {
      availablePersonas.value = data.personas
    }
  } catch {
    // 回退预置
  }
}

const onPersonaUpdated = async (newRole?: string) => {
  await loadPersonas()
  if (newRole) {
    const key = `persona_${newRole}`
    if (!treeSelectValues.value.includes(key)) {
      treeSelectValues.value.push(key)
      onDiscussTreeChange(treeSelectValues.value)
    }
  }
}
// P1-1：GSAP 动画降级（prefers-reduced-motion）
const { prefersReduced } = useReducedMotion()

const copiedMsgId = ref<string | number | null>(null)
let copiedResetTimer: ReturnType<typeof setTimeout> | null = null

/** P5-3：空态快捷入口（图标 + 动词-名词，与 HomeView 步骤条同语言） */
const quickStarts = [
  { to: '/upload', label: '上传文档', icon: Upload, iconClass: 'text-[var(--text-secondary)]' },
  { to: '/documents', label: '阅读文档', icon: Document, iconClass: 'text-[var(--text-secondary)]' },
  { to: '/quiz', label: '生成练习题', icon: DocumentChecked, iconClass: 'text-[var(--text-secondary)]' }
]

/** P7：最新一条 assistant 消息索引（动画球挂载点；-1 = 无） */
const lastAssistantIdx = computed(() => {
  for (let i = chatStore.messages.length - 1; i >= 0; i--) {
    if (chatStore.messages[i].role === 'assistant') return i
  }
  return -1
})

async function copyMessage(msg: ChatStreamMessage): Promise<void> {
  try {
    await navigator.clipboard.writeText(msg.content)
    copiedMsgId.value = msg.id
    if (copiedResetTimer) clearTimeout(copiedResetTimer)
    copiedResetTimer = setTimeout(() => { copiedMsgId.value = null }, 2000)
  } catch (e) {
    console.error('Copy failed:', e)
  }
}

const { renderMarkdown: renderMarkdownBase } = useMarkdown()

const MD_CACHE_LIMIT = 200
const _mdCache = new Map<string, string>()

function _mdCacheGet(key: string): string | undefined {
  if (!_mdCache.has(key)) return undefined
  const val = _mdCache.get(key)
  _mdCache.delete(key)
  _mdCache.set(key, val!)
  return val
}

function _mdCacheSet(key: string, val: string): void {
  if (_mdCache.size >= MD_CACHE_LIMIT) {
    const oldest = _mdCache.keys().next().value
    if (oldest !== undefined) _mdCache.delete(oldest)
  }
  _mdCache.set(key, val)
}

/** P6-2 / 阶段四B：占位符 → 来源角标（解析后还原；流式残缺标记已在解析前隐藏） */
function _applySourceBadges(html: string): string {
  return finalizeCitationHtml(html)
}

/** P6-2：单块 markdown 渲染（带缓存键前缀区分流式尾块） */
function _renderBlock(block: string, cachePrefix: string, forStreaming = false): string {
  const key = cachePrefix + block
  const cached = _mdCacheGet(key)
  if (cached) return cached
  // 解析前换出 [来源N] 占位符（并隐藏流式残缺标记），解析后还原为角标
  const prepared = prepareCitationMarkdown(block, forStreaming)
  const rendered = _applySourceBadges(renderMarkdownBase(prepared))
  _mdCacheSet(key, rendered)
  return rendered
}

/**
 * P6-2：分段流式渲染。
 * 按空行（\n\n）把内容切成块：除尾块外的"稳定块"走缓存（流式期间不变，零重算），
 * 尾块（正在生成的段落）每 token 实时 md 渲染（cachePrefix 不同避免污染稳定缓存）。
 * 效果：流式全程都是真正的 markdown 呈现（无星号井号闪现、无结束瞬间的格式跳变），
 * 每 token 只重渲染最后一个块，长回答性能 O(尾块) 而非 O(全文)。
 */
function renderMarkdown(text: string, isStreaming = false): string {
  if (!text) return ''
  if (!isStreaming) {
    // 完成态：整文单键缓存（历史会话加载等场景命中率最高）
    const key = 'full:' + text
    const cached = _mdCacheGet(key)
    if (cached) return cached
    const prepared = prepareCitationMarkdown(text, false)
    const rendered = _applySourceBadges(renderMarkdownBase(prepared))
    _mdCacheSet(key, rendered)
    return rendered
  }
  // 流式：先隐藏尾部残缺 [来源… 标记，再分块
  const safeText = hideIncompleteCitationTail(text, true)
  const blocks = safeText.split(/\n\n+/)
  const parts: string[] = []
  for (let i = 0; i < blocks.length - 1; i++) {
    parts.push(_renderBlock(blocks[i], 'stable:'))
  }
  // 尾块单独渲染（可能是不完整 md：语法闭合由 markdown-it 容错，未闭合标记按原样呈现，
  // 下个 token 到达即修正——这也是所见即所得的正确语义）
  const tail = blocks[blocks.length - 1]
  if (tail) parts.push(_renderBlock(tail, 'tail:', true))
  // 块级 HTML 直接拼接（md-it 输出已带块级结构）
  return parts.join('')
}

function scrollToSource(index: number): void {
  // 展开包含该来源的所有消息的完整来源卡
  for (const m of chatStore.messages) {
    if (m.sources && m.sources.some(s => s.index === index)) {
      m.expandedSources = true
    }
  }
  setTimeout(() => {
    const card = document.getElementById(`source-card-${index}`)
    if (card) {
      card.scrollIntoView({ behavior: 'smooth', block: 'center' })
      card.classList.add('source-card-highlighted')
      setTimeout(() => card.classList.remove('source-card-highlighted'), 2500)
    }
  }, 100)
}

async function handleSend(content: string, modelOverride?: string): Promise<void> {
  if (chatMode.value === 'discuss') {
    collapseAllSourceCards()
    await handleDiscuss(content)
    await nextTick()
    forceScrollToBottom()
    return
  }
  // 新一轮：收起此前展开的参考来源，保证新消息可见
  collapseAllSourceCards()
  const attachmentIds = collectReadyAttachmentIds()
  // 启动流式但不等结束：立刻让「刚发出的 user + 占位回答」进入可视区
  const streamPromise = chatStore.askQuestionStream(
    content, selectedDocs.value, null, researchMode.value, attachmentIds, modelOverride
  )
  void nextTick().then(() => {
    forceScrollToBottom()
    scrollLatestUserMessageIntoView()
  })
  try {
    await streamPromise
  }
  catch (_e) {
    playScene('exclaim')
    return
  }
  // 发送成功后清空本会话输入附件（临时附件已注入上下文）
  if (attachmentIds.length) {
    chatAttachments.value = []
  }
  await nextTick()
  forceScrollToBottom()
}

/** 讨论模式 SSE AbortController — 与问答流 cancelStream 对齐，供「停止」按钮使用 */
let discussAbortController: AbortController | null = null

async function handleDiscuss(content: string): Promise<void> {
  // 使用原生 fetch 调用 /chat/discuss SSE 端点
  discussAbortController?.abort()
  const controller = new AbortController()
  discussAbortController = controller
  const token = localStorage.getItem('token')
  // 失败时等 isStreaming 落下后再播 alert：avatarMood 在 streaming 期间锁死 thinking
  let pendingAlert = false

  chatStore.isStreaming = true

  // 添加用户消息
  chatStore.messages.push({
    id: Date.now(), role: 'user', content,
    created_at: new Date().toISOString(),
  })

  // 创建讨论容器消息
  const discussionMsgId = crypto.randomUUID()
  chatStore.messages.push({
    id: discussionMsgId,
    role: 'discussion',
    content: '',
    personas: [],
    discussionTurns: [],
    currentSpeaker: null,
    sources: [],
    used_source_indices: [],
    filtered_sources: [],
    expandedSources: false,
    created_at: new Date().toISOString(),
    isStreaming: true,
  })
  void nextTick().then(() => forceScrollToBottom())

  try {
    const res = await fetch(withBase('/api/chat/discuss'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        question: content,
        document_ids: selectedDocs.value,
        personas: selectedPersonas.value.length > 0
          ? selectedPersonas.value.map(role => {
              const p = availablePersonas.value.find(item => item.role === role)
              return {
                id: p?.id,
                role,
                name: p?.name || role,
                avatar: p?.avatar || 'User',
                color: p?.color,
                system_message: p?.system_message || undefined
              }
            })
          : null,
        max_turns: discussMaxTurns.value || 2,
        context_mode: discussContextMode.value,
        session_id: chatStore.currentSession || null,
      }),
      signal: controller.signal,
    })

    if (!res.ok) throw new Error(`HTTP ${res.status}`)

    const reader = res.body?.getReader()
    const decoder = new TextDecoder()
    if (!reader) throw new Error('No response body')

    const msg = chatStore.messages.find((m: any) => m.id === discussionMsgId)
    const personaBlocks: Record<string, { avatar: string; color?: string; lines: string[] }> = {}
    // 跨 chunk 缓冲，避免 TCP 分片切断 SSE 行导致 JSON 解析失败
    let sseBuffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      sseBuffer += decoder.decode(value, { stream: true })
      const lines = sseBuffer.split('\n')
      sseBuffer = lines.pop() ?? ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const payload = line.slice(6)
        if (payload === '[DONE]') continue
        try {
          const event = JSON.parse(payload)
          const _msg = msg!

          if (event.type === 'session') {
            if (event.session_id) {
              chatStore.currentSession = event.session_id
              if (!chatStore.currentSessionTitle) {
                chatStore.currentSessionTitle = content.slice(0, 50)
              }
            }
          }
          else if (event.type === 'persona_start') {
            const p = event.persona
            const matchedP = availablePersonas.value.find(item => item.name === p || item.role === p)
            const avatar = event.avatar || matchedP?.avatar || 'User'
            const color = event.color || matchedP?.color || '#3b82f6'
            const turn = event.turn || 1

            _msg.currentSpeaker = {
              name: p,
              avatar,
              color,
              action: turn > 1 ? '正在针对前序观点进行深度互辩…' : '正在梳理思路并阐述见解…'
            }

            if (!_msg.discussionTurns) _msg.discussionTurns = []
            _msg.discussionTurns.push({
              id: `turn-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
              persona: p,
              avatar,
              color,
              content: '',
              turn,
              isStreaming: true,
            })
          }
          else if (event.type === 'persona_chunk') {
            const p = event.persona
            const delta = event.delta || ''
            if (_msg.discussionTurns && _msg.discussionTurns.length > 0) {
              const activeTurn = _msg.discussionTurns[_msg.discussionTurns.length - 1]
              if (activeTurn && activeTurn.persona === p) {
                activeTurn.content += delta
              }
            }
            // 兼容 legacy personas 聚合
            if (!personaBlocks[p]) {
              const matchedP = availablePersonas.value.find(item => item.name === p || item.role === p)
              personaBlocks[p] = {
                avatar: matchedP?.avatar || 'User',
                color: matchedP?.color,
                lines: ['']
              }
            }
            personaBlocks[p].lines[personaBlocks[p].lines.length - 1] += delta
            _msg.personas = Object.entries(personaBlocks).map(([name, block]) => ({
              name,
              avatar: block.avatar,
              color: block.color,
              content: block.lines.join('\n\n'),
            }))
            _msg.content = _msg.discussionTurns?.map(t => `【${t.persona}】：${t.content}`).join('\n\n') || ''
          }
          else if (event.type === 'persona_speak') {
            const p = event.persona
            const turn = event.turn || 1
            if (_msg.discussionTurns && _msg.discussionTurns.length > 0) {
              const activeTurn = _msg.discussionTurns[_msg.discussionTurns.length - 1]
              if (activeTurn && activeTurn.persona === p) {
                activeTurn.content = event.content || activeTurn.content
                activeTurn.isStreaming = false
              }
            } else {
              // 降级支持：如果未发 persona_start 直接发 persona_speak
              const matchedP = availablePersonas.value.find(item => item.name === p || item.role === p)
              if (!_msg.discussionTurns) _msg.discussionTurns = []
              _msg.discussionTurns.push({
                id: `turn-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
                persona: p,
                avatar: event.avatar || matchedP?.avatar || 'User',
                color: event.color || matchedP?.color || '#3b82f6',
                content: event.content,
                turn,
                isStreaming: false,
              })
            }

            if (!personaBlocks[p]) {
              const matchedP = availablePersonas.value.find(item => item.name === p || item.role === p)
              personaBlocks[p] = {
                avatar: event.avatar || matchedP?.avatar || 'User',
                color: event.color || matchedP?.color,
                lines: []
              }
            }
            personaBlocks[p].lines.push(event.content)
            _msg.personas = Object.entries(personaBlocks).map(([name, block]) => ({
              name,
              avatar: block.avatar,
              color: block.color,
              content: block.lines.join('\n\n'),
            }))

            if (_msg.currentSpeaker?.name === p) {
              _msg.currentSpeaker = null
            }
          }
          else if (event.type === 'summary_start') {
            _msg.currentSpeaker = {
              name: '主持人',
              avatar: 'ChatDotSquare',
              color: '#10b981',
              action: '正在归纳核心共识与学习建议…'
            }
            _msg.summary = ''
            _msg.summaryStreaming = true
          }
          else if (event.type === 'summary_chunk') {
            _msg.summary = (_msg.summary || '') + (event.delta || '')
            _msg.summaryStreaming = true
          }
          else if (event.type === 'summary') {
            _msg.summary = event.content
            _msg.summaryStreaming = false
            _msg.currentSpeaker = null
            _msg.content += '\n\n---\n\n**讨论总结**\n\n' + event.content
          }
          else if (event.type === 'error') {
            // 讨论失败 → 保留后端友好错误信息 + 球体 alert（飞行中出事）
            const errText = String(event.message || '讨论生成失败，请稍后重试')
            _msg.isStreaming = false
            _msg.currentSpeaker = null
            _msg.error = errText
            _msg.content = _msg.content
              ? _msg.content + '\n\n---\n\n' + errText
              : errText
            pendingAlert = true
          }
          else if (event.type === 'done') {
            _msg.isStreaming = false
            _msg.currentSpeaker = null
            if (_msg.discussionTurns) {
              _msg.discussionTurns.forEach(t => { t.isStreaming = false })
            }
            _msg.summaryStreaming = false
            // 新会话研讨完成后，刷新历史列表让侧边栏能看到它
            if (
              chatStore.currentSession &&
              !chatStore.sessions.some(s => s.session_id === chatStore.currentSession)
            ) {
              chatStore.fetchSessions(true).catch(() => {})
            }
          }
        }
        catch { /* skip malformed */ }
      }
      await nextTick()
      forceScrollToBottom()
    }
  }
  catch (e: any) {
    if (e.name !== 'AbortError') {
      const msg = chatStore.messages.find((m: any) => m.id === discussionMsgId)
      if (msg) {
        msg.error = `讨论失败：${e.message}`
        msg.content = msg.error
        msg.isStreaming = false
        msg.currentSpeaker = null
      }
      pendingAlert = true
    }
  }
  finally {
    chatStore.isStreaming = false
    if (discussAbortController === controller) {
      discussAbortController = null
    }
    if (pendingAlert) playScene('alert')
  }
}

function handleStop(): void {
  // 中止进行中的研讨 SSE（若有）
  discussAbortController?.abort()
  discussAbortController = null
  chatStore.cancelStream()
  // P8：用户中止 → 眨眼示意
  playScene('cancelled')
}

function exportChat(): void {
  if (chatStore.messages.length === 0) return
  const md = buildChatMarkdown(chatStore.messages, chatStore.currentSessionTitle || '对话')
  downloadChatMarkdown(md)
  // P8：导出完成 → 彗尾飘移
  playScene('comet')
}

function newChat(): void {
  // P8：清空有内容的会话 → burst 爆散
  if (chatStore.messages.length > 0) {
    playScene('burst')
  }
  collapseAllSourceCards()
  chatStore.clearMessages()
  chatStore.currentSession = null
  chatStore.currentSessionTitle = ''
  showHistory.value = false
}

/** 参考来源自动折叠：新一轮对话 / 新会话 / 重进历史时强制收起 */
function collapseAllSourceCards(): void {
  for (const m of chatStore.messages) {
    m.expandedSources = false
  }
}

function onSessionLoaded(_sessionId: string): void {
  showHistory.value = false
  // 历史 DOM + Markdown/图片高度会晚于 nextTick 稳定 → 多帧贴底
  collapseAllSourceCards()
  scrollChatToBottomSticky(8)
  // P8：载入历史会话 → orbit 入场
  playScene('arrive')
  // 5.5 断线续流：历史载入后若末条未完成则自动续流
  void chatStore.tryResumeIncomplete()
}

// ── 5.6 聊天附件：会话临时上传，两阶段状态 ─────────────────────────────────
const chatAttachments = ref<ChatAttachmentItem[]>([])

function isImageFile(file: File): boolean {
  return (file.type || '').startsWith('image/') || /\.(png|jpe?g|gif|webp|bmp)$/i.test(file.name)
}

async function addChatAttachments(files: File[]): Promise<void> {
  for (const file of files) {
    const localId = `local-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    const item: ChatAttachmentItem = {
      id: localId,
      filename: file.name,
      file_type: isImageFile(file) ? 'image' : 'document',
      status: 'uploading',
      size: file.size,
    }
    chatAttachments.value = [...chatAttachments.value, item]
    try {
      const form = new FormData()
      form.append('file', file)
      const sessionId = chatStore.currentSession || ''
      const { data } = await api.post(
        `/documents/chat-attachments/upload${sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ''}`,
        form,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      )
      const idx = chatAttachments.value.findIndex(a => a.id === localId)
      if (idx !== -1) {
        chatAttachments.value[idx] = {
          id: data.id,
          filename: data.filename || file.name,
          file_type: (data.file_type === 'image' ? 'image' : 'document'),
          // uploaded/parsing/ready：上传完成即可发送，解析可后台继续
          status: data.status || 'ready',
          size: data.size ?? file.size,
        }
        chatAttachments.value = [...chatAttachments.value]
      }
    } catch (e) {
      console.error('Attachment upload failed:', e)
      const idx = chatAttachments.value.findIndex(a => a.id === localId)
      if (idx !== -1) {
        chatAttachments.value[idx] = { ...chatAttachments.value[idx], status: 'error' }
        chatAttachments.value = [...chatAttachments.value]
      }
    }
  }
}

async function removeChatAttachment(id: string): Promise<void> {
  chatAttachments.value = chatAttachments.value.filter(a => a.id !== id)
  if (!id.startsWith('local-')) {
    try {
      await api.delete(`/documents/chat-attachments/${id}`)
    } catch {
      /* 已移除本地态，服务端残留可稍后清理 */
    }
  }
}

function collectReadyAttachmentIds(): string[] {
  // 仅「上传中」会阻塞发送（ChatInput 已禁用）；parsing/ready 一并带上
  return chatAttachments.value
    .filter(a => a.status !== 'uploading' && a.status !== 'error' && !a.id.startsWith('local-'))
    .map(a => a.id)
}

function onSessionDeleted(sessionId: string): void {
  if (chatStore.currentSession === sessionId) {
    newChat()
  }
}

function scrollToBottom(): void {
  if (messagesRef.value) {
    const el = messagesRef.value
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100
    if (nearBottom) {
      el.scrollTop = el.scrollHeight
    }
  }
}

/** 无条件滚到底：历史载入 / 用户主动发送后使用（不受 nearBottom 限制） */
function forceScrollToBottom(): void {
  if (!messagesRef.value) return
  const el = messagesRef.value
  el.scrollTop = el.scrollHeight
}

/**
 * 连续多帧贴底：等 Markdown/图片/思考面板撑开后再滚，避免历史会话停在随机位置。
 */
function scrollChatToBottomSticky(attempts = 6): void {
  let i = 0
  const tick = (): void => {
    forceScrollToBottom()
    if (++i < attempts) {
      requestAnimationFrame(() => {
        window.setTimeout(tick, 40)
      })
    }
  }
  nextTick(() => tick())
}

/**
 * 发送后把刚发出的 user 消息滚进可视区（优先贴底，保证占位回答也可见）。
 */
function scrollLatestUserMessageIntoView(): void {
  const container = messagesRef.value
  if (!container) {
    forceScrollToBottom()
    return
  }
  // 刚发送时目标是「看到最新对话」，贴底最稳；仅在容器尚未增长时兜底用 user 锚点
  forceScrollToBottom()
  const items = container.querySelectorAll('[data-msg-role="user"]')
  const target = items[items.length - 1] as HTMLElement | undefined
  if (target) {
    const cRect = container.getBoundingClientRect()
    const tRect = target.getBoundingClientRect()
    // 若 user 消息被输入区/容器底裁切，再把它上移到容器下部 1/3
    if (tRect.bottom > cRect.bottom - 8) {
      container.scrollTop += tRect.bottom - (cRect.top + cRect.height * 0.66)
    }
  }
}

let gsapCtx: gsap.Context | null = null

/**
 * P8：mood 从消息状态推导。流式生成期间全心投入思考（thinking 真版三点），
 * 生成完毕转为完成庆祝（done），空闲回归 idle。
 */
function updateBotMood(msg: ChatStreamMessage, isLast: boolean): void {
  if (!isLast || msg.role !== 'assistant') { botMood.value = 'idle'; return }
  if (msg.isStreaming) {
    botMood.value = 'thinking'
  } else {
    botMood.value = 'done'
  }
}

/** P8：一次性场景 mood（orbit/burst/comet 等），到点回收优先权交还消息推导 */
const sceneMood = ref<BotMood | null>(null)
let sceneTimer: ReturnType<typeof setTimeout> | null = null

/** 各场景编排总时长（ms） */
const SCENE_DURATION: Partial<Record<BotMood, number>> = {
  arrive: 6000,
  burst: 5000,
  comet: 4800,
  exclaim: 4200,
  alert: 4200,
  cancelled: 4200
}

function playScene(mood: BotMood): void {
  sceneMood.value = mood
  if (sceneTimer) clearTimeout(sceneTimer)
  sceneTimer = setTimeout(() => { sceneMood.value = null }, SCENE_DURATION[mood] ?? 5000)
}

/** 渲染给球的 mood：流式生成期间锁死 thinking 全神贯注思考，否则优先场景覆盖，再走消息推导 */
const avatarMood = computed<BotMood>(() => {
  if (chatStore.isStreaming) return 'thinking'
  return sceneMood.value ?? botMood.value
})

/**
 * P8-4：表情随 mood 换脸（引擎内 morph，不重置时钟）。
 * answering=专注 / done=愉悦 / thinking=审慎 / egg=疑惑 / sleep=困倦。
 * arrive/burst/comet 大戏保持 neutre——它们的表情就是状态本身
 * （states.ts baseFace:false 契约：非 idle 态自带测量表情，不可替换）。
 */
const avatarExpr = computed<ExpressionId>(() => {
  switch (avatarMood.value) {
    case 'sleep': return 'somnolent'
    case 'answering': return 'attentif'
    case 'done': return 'heureux'
    case 'thinking': return 'mefiant'
    case 'egg': return 'confus'
    case 'exclaim': return 'surpris'
    case 'alert': return 'surpris'
    case 'cancelled': return 'blase'
    default: return 'neutre'
  }
})

/* ---------------- P8-2：空闲打瞌睡 ---------------- */
const IDLE_MS = 90_000   // 90s 无操作才打瞌睡（原 30s 太敏感，切个后台就触发）

/** 鼠标是否悬停在对话区域内：
 *  是 → 指针事件不复位 idle（注视跟踪已证明鼠标在线，不应同时驱动 idle）；
 *  否 → 指针/键盘都算 activity。
 */
const mouseInChat = ref(false)

/** 两种 idle 变体交替播放：弹跳 → 蛋形脉动 → 弹跳 → ... */
const IDLE_VARIANTS: readonly BotMood[] = ['sleep', 'egg'] as const
/** 每个变体播放约 5-6s（sleep mood blocks 5.0s / egg 2.8s，取 6s 覆盖最长） */
const VARIANT_MS = 6_000

let idleTimer: ReturnType<typeof setTimeout> | null = null
let sleepPhaseTimer: ReturnType<typeof setTimeout> | null = null
let sleepVariant = 0
// 非 Reactivity 变量：事件处理器引用（用于 add/removeEventListener 成对）
let _onPointer: ((e: Event) => void) | null = null
let _onKey: ((e: Event) => void) | null = null

/** 排入下一个变体切换（仅在球处于 idle 态时才切） */
function scheduleVariant(): void {
  sleepPhaseTimer = setTimeout(() => {
    if (botMood.value !== 'sleep' && botMood.value !== 'egg') return
    sleepVariant = (sleepVariant + 1) % IDLE_VARIANTS.length
    botMood.value = IDLE_VARIANTS[sleepVariant]
    scheduleVariant()
  }, VARIANT_MS)
}

function enterSleep(): void {
  // 尊重用户偏好中的打瞌睡开关：若关闭则不自动进入瞌睡
  if (!prefs.value.botIdleSleep) return
  // 流式中永不瞌睡（球有活干）
  if (chatStore.isStreaming) return
  sleepVariant = 0
  botMood.value = IDLE_VARIANTS[0]
  scheduleVariant()
}

function onActivity(e?: Event): void {
  // 鼠标悬停在对话区时，pointer 事件不复位 idle（注视跟踪已证明人在用鼠标）
  if (e instanceof PointerEvent && mouseInChat.value) return
  if (idleTimer) clearTimeout(idleTimer)
  if (sleepPhaseTimer) clearTimeout(sleepPhaseTimer)
  sleepPhaseTimer = null
  idleTimer = setTimeout(enterSleep, IDLE_MS)
  // 从瞌睡中被唤醒 → acknowledge 点头示意
  if (botMood.value === 'sleep' || botMood.value === 'egg') {
    botMood.value = 'acknowledge'
  }
}

watch(
  () => {
    const last = chatStore.messages[chatStore.messages.length - 1]
    return last ? { last } : null
  },
  (v) => {
    if (v) {
      updateBotMood(v.last, true)
      // P6-3：流式内容增长时跟随滚动（scrollToBottom 内部有 nearBottom 判断，
      // 用户手动上滚回看时不会被打扰）
      if (v.last.isStreaming) nextTick(() => scrollToBottom())
    } else {
      botMood.value = 'idle'
    }
  },
  { deep: true }
)

/** P7-FLIP：首条消息发送时球从空态居中飞到最新消息作者行。
 *  pre 时机（DOM 未更新）抓旧球 rect；nextTick 新 DOM 就位后反演动画。 */
let flipPending = false
let flipFromRect: DOMRect | null = null

watch(() => chatStore.messages.length, (newLen, oldLen) => {
  if (oldLen === 0 && newLen > 0) {
    const first = chatStore.messages[0]
    // 仅真实发送（首条是 user）才 FLIP；历史会话批量载入直接落位
    const isLiveSend = first?.role === 'user'
    const oldEl = document.querySelector('.bot-avatar-flip') as HTMLElement | null
    if (oldEl && isLiveSend && !prefersReduced.value) {
      flipPending = true
      // 旧元素即将销毁，rect 存模块变量（dataset 会随元素销毁丢失）
      flipFromRect = oldEl.getBoundingClientRect()
    }
  }
  const grew = newLen > oldLen
  const replacedHistory = newLen > 0 && oldLen > 0 && newLen !== oldLen
  nextTick(() => {
    if (flipPending) {
      flipPending = false
      playFlip()
    }
    // 新消息/历史切换：强制贴底；仅流式同长度增长走 nearBottom 跟随
    if (grew || replacedHistory) {
      if (replacedHistory) scrollChatToBottomSticky(4)
      else forceScrollToBottom()
    } else {
      scrollToBottom()
    }
    const last = chatStore.messages[newLen - 1]
    if (last) updateBotMood(last, true)
  })
})

/** P7-FLIP 播放：旧 rect（模块变量）→ 新 rect，反演位移+缩放（120px→48px） */
function playFlip(): void {
  const newEl = document.querySelector('.bot-avatar-flip') as HTMLElement | null
  if (!newEl || !flipFromRect) return
  try {
    const from = flipFromRect
    flipFromRect = null
    const to = newEl.getBoundingClientRect()
    const dx = from.left + from.width / 2 - (to.left + to.width / 2)
    const dy = from.top + from.height / 2 - (to.top + to.height / 2)
    const scale = from.width / to.width
    gsap.from(newEl, {
      x: dx, y: dy, scale,
      duration: 0.55,
      ease: 'power3.inOut',
      clearProps: 'x,y,scale'
    })
  } catch {
    /* rect 解析失败则跳过动画（球已在正确位置） */
  }
}

/** P0-A 起始问题：可关闭并记住 */
const STARTERS_DISMISS_KEY = 'study-copilot.starters-dismissed'
const startersDismissed = ref(localStorage.getItem(STARTERS_DISMISS_KEY) === '1')
function dismissStarters(): void {
  startersDismissed.value = true
  localStorage.setItem(STARTERS_DISMISS_KEY, '1')
}

onMounted(async () => {
  // P8-2：空闲瞌睡——活动重置计时（瞌睡本身即低动效，不受动画偏好影响）
  _onPointer = (e) => onActivity(e)
  _onKey = (e) => onActivity(e)
  window.addEventListener('pointerdown', _onPointer, { passive: true })
  window.addEventListener('keydown', _onKey, { passive: true })
  onActivity()
  // 离开页面后再进入：来源卡一律折叠
  collapseAllSourceCards()

  await nextTick()
  // 消息 DOM id 与 proximity sections 对齐：msg-${id}

  await chatStore.fetchSessions()
  await Promise.allSettled([
    documentStore.fetchDocuments(),
    courseStore.fetchCourses(),
  ])

  await loadPersonas()

  if (documentStore.documents.length > 0) {
    selectedDocs.value = documentStore.documents
      .filter(d => d.status === 'ready')
      .slice(0, 1)
      .map(d => d.id)
  }

  // P0-A 空态起始问题（未关闭且当前无消息时拉取）
  if (!startersDismissed.value && chatStore.messages.length === 0) {
    void chatStore.loadStarterSuggestions(selectedDocs.value)
  }

  // F9：选中文档集合变化 → 旧问题清空并按新集合重生成（缓存键含 doc ids）
  watch(
    () => [...selectedDocs.value].sort().join(','),
    () => {
      if (startersDismissed.value) return
      if (chatStore.messages.length > 0) return
      void chatStore.loadStarterSuggestions(selectedDocs.value)
    }
  )

  const contextQuery = route.query.context
  const docId = route.query.docId

  if (docId && !selectedDocs.value.includes(docId as string)) {
    selectedDocs.value = [docId as string]
  }

  if (contextQuery) {
    await handleSend(contextQuery as string)
  }

  // 5.5 断线续流：挂载后若末条 assistant 未完成则自动续流
  void chatStore.tryResumeIncomplete()

  // P1-1：减少动态偏好下不执行入场动画
  if (prefersReduced.value) return
  gsapCtx = gsap.context(() => {
    const emptyIcon = messagesRef.value?.querySelector('.w-20.h-20')
    if (emptyIcon) {
      gsap.from(emptyIcon, { scale: 0.8, opacity: 0, duration: 0.5, ease: 'back.out(1.2)' })
    }
  }, messagesRef.value ?? undefined)
})

onUnmounted(() => {
  gsapCtx?.revert()
  if (copiedResetTimer) clearTimeout(copiedResetTimer)
  // P8：清理场景/空闲/变体计时器与全局监听
  if (idleTimer) clearTimeout(idleTimer)
  if (sleepPhaseTimer) clearTimeout(sleepPhaseTimer)
  if (sceneTimer) clearTimeout(sceneTimer)
  if (_onPointer) window.removeEventListener('pointerdown', _onPointer)
  if (_onKey) window.removeEventListener('keydown', _onKey)
  window.removeEventListener('pointermove', onActivity)
  window.removeEventListener('pointerleave', onActivity)
})
</script>

<style>
/* 精修（批次3）：中文正文行高 1.7（舒适区），作用于 AI 回答正文 */
.prose {
  line-height: 1.75;
  font-size: 0.9rem;
}
.prose p {
  margin-bottom: 0.5em;
}
.prose p:last-child {
  margin-bottom: 0;
}
.prose ul, .prose ol {
  margin-top: 0.4em;
  margin-bottom: 0.6em;
  padding-left: 1.4em;
}
.prose li {
  margin-bottom: 0.25em;
}
.prose h1, .prose h2, .prose h3, .prose h4 {
  margin-top: 0.7em;
  margin-bottom: 0.3em;
  font-weight: 600;
  line-height: 1.4;
}
/* DESIGN.md link-on-dark/light：链接 = text-link 色 + 持久下划线（品牌签名） */
.prose a {
  color: var(--text-link);
  text-decoration: underline;
  text-decoration-color: var(--border-hover);
  text-underline-offset: 2px;
  transition: text-decoration-color 0.15s ease;
}
.prose a:hover {
  text-decoration-color: var(--text-link);
}
/* markdown 表格：发丝线分界 */
.prose table {
  border-collapse: collapse;
  margin: 0.6em 0;
}
.prose th, .prose td {
  border: 1px solid var(--border-default);
  padding: 0.35em 0.7em;
  font-size: 0.875rem;
}
.prose th {
  background: var(--bg-tertiary);
  font-weight: 600;
}
.prose h1:first-child, .prose h2:first-child, .prose h3:first-child, .prose h4:first-child {
  margin-top: 0;
}
.prose blockquote {
  margin: 0.6em 0;
  padding: 0.3em 0.8em;
  border-left: 2px solid var(--border-hover);
  color: var(--text-secondary);
}
.prose pre.hljs {
  background: var(--bg-tertiary);
  padding: 1rem;
  border-radius: 0.5rem;
  overflow-x: auto;
  font-size: 0.875rem;
}
.prose code {
  background: var(--bg-tertiary);
  padding: 0.125rem 0.25rem;
  border-radius: 0.25rem;
  font-size: 0.875rem;
}
.prose pre code {
  background: transparent;
  padding: 0;
}
/* WeKnora 风格引用微胶囊角标 (.source-badge) */
.prose .source-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  vertical-align: baseline;
  transform: translateY(-0.06em);
  padding: 0 5px;
  margin: 0 0.12em;
  font-size: 0.72em;
  line-height: 1.45;
  font-weight: 500;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  border-radius: 999px;
  cursor: pointer;
  white-space: nowrap;
  user-select: none;
  background: color-mix(in srgb, var(--text-primary) 5%, transparent);
  color: color-mix(in srgb, var(--text-primary) 82%, var(--text-primary));
  border: 0;
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--text-primary) 12%, transparent);
  transition: background 0.15s ease, box-shadow 0.15s ease, color 0.15s ease;
}
.prose .source-badge:hover {
  background: color-mix(in srgb, var(--text-primary) 9%, transparent);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--text-primary) 22%, transparent);
  color: var(--text-primary);
}
.dark .prose .source-badge {
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.85);
  border: 0;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.16);
}
.dark .prose .source-badge:hover {
  background: rgba(255, 255, 255, 0.15);
  color: #ffffff;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.3);
}

/* 来源卡高亮动效：解决暗色模式下纯黑 ring 隐形缺陷 */
.source-card-highlighted {
  border-color: var(--color-primary) !important;
  box-shadow: 0 0 0 2px var(--color-primary), 0 4px 12px rgba(0, 0, 0, 0.15) !important;
  background-color: var(--bg-hover) !important;
  transition: all 0.3s ease;
}
.dark .source-card-highlighted {
  border-color: rgba(255, 255, 255, 0.7) !important;
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.4), 0 0 16px rgba(255, 255, 255, 0.14) !important;
  background-color: rgba(255, 255, 255, 0.08) !important;
  transition: all 0.3s ease;
}

/* 思考过程折叠区 */
.thinking-section summary::-webkit-details-marker {
  display: none;
}
.thinking-section[open] .thinking-summary .el-icon {
  transform: rotate(90deg);
}

/* ===== P7 动画球 FLIP ===== */
/* SVG transform 默认绕视口原点——FLIP 缩放前必须中心化 */
.bot-avatar-flip {
  transform-box: fill-box;
  transform-origin: center;
}

/* ===== P5-2 动画层 ===== */
/* 新消息入场：淡入 + 轻上移（0.25s，克制的网页式节奏） */
.msg-enter {
  animation: msg-enter 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
@keyframes msg-enter {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 来源条目逐个入场（首 8 条 stagger，超出即无延迟） */
.source-stagger > button {
  animation: msg-enter 0.25s cubic-bezier(0.16, 1, 0.3, 1) backwards;
}
.source-stagger > button:nth-child(1) { animation-delay: 0s; }
.source-stagger > button:nth-child(2) { animation-delay: 0.05s; }
.source-stagger > button:nth-child(3) { animation-delay: 0.1s; }
.source-stagger > button:nth-child(4) { animation-delay: 0.15s; }
.source-stagger > button:nth-child(5) { animation-delay: 0.2s; }
.source-stagger > button:nth-child(6) { animation-delay: 0.25s; }
.source-stagger > button:nth-child(7) { animation-delay: 0.3s; }
.source-stagger > button:nth-child(8) { animation-delay: 0.35s; }

/* 思考中三点脉冲 */
.thinking-dot {
  width: 6px;
  height: 6px;
  border-radius: 9999px;
  background: var(--text-muted);
  animation: dot-pulse 1.2s ease-in-out infinite;
}
@keyframes dot-pulse {
  0%, 100% { opacity: 0.3; transform: translateY(0); }
  50% { opacity: 1; transform: translateY(-3px); }
}

/* 流式打字机光标：品牌色竖条呼吸 */
.stream-caret {
  display: inline-block;
  width: 2px;
  height: 1em;
  margin-left: 2px;
  vertical-align: text-bottom;
  background: var(--color-primary);
  animation: caret-blink 0.9s steps(1) infinite;
}
@keyframes caret-blink {
  0%, 55% { opacity: 1; }
  56%, 100% { opacity: 0; }
}

/* §6.B：减少动态偏好下全部降级（光标改静态、入场瞬时、脉冲停） */
@media (prefers-reduced-motion: reduce) {
  .msg-enter,
  .source-stagger > button,
  .thinking-dot {
    animation: none;
  }
}

/* 讨论配置树形下拉菜单美化（仅保留关键选项，悬停展示详情提示） */
.discuss-tree-popper {
  width: 176px !important;
  min-width: 176px !important;
  max-width: 220px !important;
  padding: 4px 6px !important;
}

/* 消除下拉列表默认额外内边距 */
.discuss-tree-popper .el-select-dropdown__list {
  padding: 0 !important;
}

/* 彻底清空 el-select-dropdown__item 的默认 padding、高度与多选伪元素对勾，解决选项被挤压和截断问题 */
.discuss-tree-popper .el-select-dropdown__item {
  padding: 0 !important;
  height: 28px !important;
  line-height: 28px !important;
  background-color: transparent !important;
  overflow: visible !important;
  text-overflow: clip !important;
  white-space: nowrap !important;
  flex: 1 1 auto !important;
  min-width: 0 !important;
  display: flex !important;
  align-items: center !important;
  width: 100% !important;
  box-sizing: border-box !important;
}
.discuss-tree-popper .el-select-dropdown.is-multiple .el-select-dropdown__item.is-selected:after {
  display: none !important;
}

/* 彻底隐藏所有 expand-icon（包括叶子节点的占位空白），消除选项左侧死空白 */
.discuss-tree-popper .el-tree-node__expand-icon {
  display: none !important;
}

/* 树节点内容盒模型自适应 */
.discuss-tree-popper .el-tree-node__content {
  display: flex !important;
  align-items: center !important;
  width: 100% !important;
  box-sizing: border-box !important;
}
.discuss-tree-popper .el-tree-node__label {
  flex: 1 1 auto !important;
  min-width: 0 !important;
  display: flex !important;
  align-items: center !important;
  width: 100% !important;
}

/* 一级分类标题栏：无复选框、整洁浅色背景横条，与菜单宽度自然契合 */
.discuss-tree-popper .el-tree > .el-tree-node > .el-tree-node__content > .el-checkbox {
  display: none !important;
}
.discuss-tree-popper .el-tree > .el-tree-node > .el-tree-node__content {
  cursor: default;
  background-color: var(--bg-secondary);
  border-radius: var(--radius-xs);
  margin-top: 5px;
  margin-bottom: 2px;
  padding-left: 6px !important;
  padding-right: 6px !important;
  height: 24px !important;
  line-height: 24px !important;
  pointer-events: none;
}
.discuss-tree-popper .el-tree > .el-tree-node:first-child > .el-tree-node__content {
  margin-top: 0;
}

/* 二级选项：贴左精致对齐，去除默认缩进，名称与右侧描述在 176px 宽度内完美呼应 */
.discuss-tree-popper .el-tree-node__children .el-tree-node__content {
  padding-left: 6px !important;
  padding-right: 6px !important;
  height: 28px !important;
  line-height: 28px !important;
  border-radius: var(--radius-xs);
  transition: background-color 0.15s ease;
}
.discuss-tree-popper .el-tree-node__children .el-tree-node__content:hover {
  background-color: var(--bg-tertiary);
}
.discuss-tree-popper .el-tree-node__children .el-tree-node__content .el-checkbox {
  margin-right: 6px !important;
  margin-left: 0 !important;
}

/* 讨论配置下拉：隐藏已选标签与输入框，保持"讨论配置 ⌄"简洁按钮 */
.discuss-tree-select .el-select__selection,
.discuss-tree-select .el-select__tags,
.discuss-tree-select .el-select__placeholder,
.discuss-tree-select .el-select__input-wrapper {
  display: none !important;
}
.discuss-tree-select .el-select__wrapper {
  justify-content: space-between !important;
  cursor: pointer;
  padding-left: 10px !important;
  padding-right: 8px !important;
}
</style>
