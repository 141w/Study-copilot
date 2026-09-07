<template>
  <div class="flex" :style="containerHeightStyle">
    <!-- Chat Area -->
    <div class="flex-1 flex flex-col" @mouseenter="mouseInChat = true" @mouseleave="mouseInChat = false">
      <!-- Top Bar -->
      <div class="border-b border-[var(--border-default)] px-4 sm:px-6 py-2.5 bg-[var(--surface-card)] flex items-center justify-between gap-3 overflow-x-auto">
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

      <!-- Document Selector -->
      <div class="border-b border-[var(--border-default)] px-6 py-3 bg-[var(--bg-secondary)]">
        <DocumentPicker v-model="selectedDocs" mode="multiple" label="参考文档" :documents="readyDocs" />
      </div>

      <!-- Messages Area -->
      <div ref="messagesRef" class="flex-1 overflow-y-auto">
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
        </div>

        <div v-else class="max-w-3xl mx-auto px-4 py-6 space-y-6">
          <!-- P7：assistant 尚未响应时（仅 user 消息），球暂驻顶部（FLIP 落点） -->
          <div v-if="lastAssistantIdx === -1" class="flex items-center gap-2.5">
            <CopilotBotAvatar class="bot-avatar-flip" :size="48" :mood="avatarMood" :expression="avatarExpr" />
          </div>

          <template v-for="(msg, idx) in chatStore.messages" :key="idx">
            <!-- Discussion mode -->
            <ChatDiscussionItem
              v-if="msg.role === 'discussion'"
              :message="msg"
            />

            <!-- Regular Assistant / User message -->
            <ChatMessageItem
              v-else
              :message="msg"
              :rendered-markdown="renderMarkdown(msg.content, msg.isStreaming)"
              :show-avatar="idx === lastAssistantIdx"
              :is-latest-assistant="msg === chatStore.messages[chatStore.messages.length - 1]"
              :avatar-mood="avatarMood"
              :avatar-expr="avatarExpr"
              :is-copied="copiedMsgId === msg.id"
              @copy="copyMessage"
              @scroll-to-source="scrollToSource"
            />
          </template>
        </div>
      </div>

      <!-- Input Area -->
      <div class="bg-[var(--surface-card)]">
        <div class="max-w-3xl mx-auto px-4 pb-4 pt-2">
          <ChatInput
            @send="handleSend"
            @stop="handleStop"
            :loading="chatStore.isStreaming"
            placeholder="输入问题，按 Enter 发送..."
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
import type { ChatStreamMessage } from '../stores/chat'
import type { BotMood } from '../components/CopilotBotAvatar.vue'
import type { ExpressionId } from '../bot/expressions'
import { useDocumentStore } from '../stores/document'
import ChatInput from '../components/chat/ChatInput.vue'
import ChatHistoryPanel from '../components/chat/ChatHistoryPanel.vue'
import DocumentPicker from '../components/common/DocumentPicker.vue'
import ChatMessageItem from '../components/chat/ChatMessageItem.vue'
import ChatDiscussionItem from '../components/chat/ChatDiscussionItem.vue'
import PersonaManageDialog from '../components/chat/PersonaManageDialog.vue'
import { useVisualViewport } from '../composables/useVisualViewport'
import { buildChatMarkdown, downloadChatMarkdown } from '../composables/useChatExport'
import { useMarkdown } from '../composables/useMarkdown'
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
const readyDocs = computed(() => documentStore.readyDocuments)
const selectedDocs = ref<string[]>([])
const showHistory = ref(false)
const showPersonaDialog = ref(false)
const botMood = ref<BotMood>('idle')
const messagesRef = ref<HTMLElement | null>(null)
const route = useRoute()
const chatMode = ref<'qa' | 'discuss'>('qa')
// 讨论上下文模式（rag_snippets=检索片段 / full_docs=全文打包）
const discussContextMode = ref<'rag_snippets' | 'full_docs'>('rag_snippets')
const discussMaxTurns = ref<number>(2)

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

/** P6-2：来源标记 → 可点击角标（渲染后处理，稳定块缓存命中时同样适用） */
function _applySourceBadges(html: string): string {
  return html.replace(/\[来源(\d+)\]/g, (_match, num: string) => {
    return `<sup class="source-badge" data-index="${num}">[${num}]</sup>`
  })
}

/** P6-2：单块 markdown 渲染（带缓存键前缀区分流式尾块） */
function _renderBlock(block: string, cachePrefix: string): string {
  const key = cachePrefix + block
  const cached = _mdCacheGet(key)
  if (cached) return cached
  const rendered = _applySourceBadges(renderMarkdownBase(block))
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
    const rendered = _applySourceBadges(renderMarkdownBase(text))
    _mdCacheSet(key, rendered)
    return rendered
  }
  const blocks = text.split(/\n\n+/)
  const parts: string[] = []
  for (let i = 0; i < blocks.length - 1; i++) {
    parts.push(_renderBlock(blocks[i], 'stable:'))
  }
  // 尾块单独渲染（可能是不完整 md：语法闭合由 markdown-it 容错，未闭合标记按原样呈现，
  // 下个 token 到达即修正——这也是所见即所得的正确语义）
  const tail = blocks[blocks.length - 1]
  if (tail) parts.push(_renderBlock(tail, 'tail:'))
  // 块级 HTML 直接拼接（md-it 输出已带块级结构）
  return parts.join('')
}

function scrollToSource(index: number): void {
  const lastMsg = chatStore.messages[chatStore.messages.length - 1]
  if (lastMsg && lastMsg.role === 'assistant') {
    const msgIndex = chatStore.messages.length - 1
    chatStore.messages[msgIndex].expandedSources = !chatStore.messages[msgIndex].expandedSources
    setTimeout(() => {
      const card = document.getElementById(`source-card-${index}`)
      if (card) {
        card.scrollIntoView({ behavior: 'smooth', block: 'center' })
        card.classList.add('ring-2', 'ring-[var(--color-navy)]', 'bg-[var(--color-primary-light)]')
        setTimeout(() => card.classList.remove('ring-2', 'ring-[var(--color-navy)]', 'bg-[var(--color-primary-light)]'), 3000)
      }
    }, 100)
  }
}

async function handleSend(content: string): Promise<void> {
  if (chatMode.value === 'discuss') {
    await handleDiscuss(content)
    return
  }
  try {
    await chatStore.askQuestionStream(content, selectedDocs.value)
  }
  catch (_e) {
    playScene('exclaim')
    return
  }
  await nextTick()
  scrollToBottom()
}

async function handleDiscuss(content: string): Promise<void> {
  // 使用原生 fetch 调用 /chat/discuss SSE 端点
  const controller = new AbortController()
  const token = localStorage.getItem('token')

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

  try {
    const res = await fetch('/api/chat/discuss', {
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

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const text = decoder.decode(value, { stream: true })
      const lines = text.split('\n')
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
            // 讨论失败 → 保留后端友好错误信息
            const errText = String(event.message || '讨论生成失败，请稍后重试')
            _msg.isStreaming = false
            _msg.currentSpeaker = null
            _msg.error = errText
            _msg.content = _msg.content
              ? _msg.content + '\n\n---\n\n' + errText
              : errText
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
      scrollToBottom()
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
    }
  }
}

function handleStop(): void {
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
  chatStore.clearMessages()
  chatStore.currentSession = null
  chatStore.currentSessionTitle = ''
  showHistory.value = false
}

function onSessionLoaded(_sessionId: string): void {
  nextTick(() => scrollToBottom())
  showHistory.value = false
  // P8：载入历史会话 → orbit 入场
  playScene('arrive')
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

let gsapCtx: gsap.Context | null = null

/**
 * P8：mood 从消息状态推导。egg = 流式已开始但无思考步骤也无内容
 * （等首 token 的蛋形收紧）；thinking = 有 Agentic 步骤（真版三点）。
 */
function updateBotMood(msg: ChatStreamMessage, isLast: boolean): void {
  if (!isLast || msg.role !== 'assistant') { botMood.value = 'idle'; return }
  if (!msg.isStreaming) botMood.value = 'done'
  else if (msg.content) botMood.value = 'answering'
  else if (Array.isArray(msg.thinking) && msg.thinking.length > 0) botMood.value = 'thinking'
  else botMood.value = 'egg'
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
  cancelled: 4200
}

function playScene(mood: BotMood): void {
  sceneMood.value = mood
  if (sceneTimer) clearTimeout(sceneTimer)
  sceneTimer = setTimeout(() => { sceneMood.value = null }, SCENE_DURATION[mood] ?? 5000)
}

/** 渲染给球的 mood：一次性场景播放中优先，否则走消息推导 */
const avatarMood = computed<BotMood>(() => sceneMood.value ?? botMood.value)

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
  nextTick(() => {
    if (flipPending) {
      flipPending = false
      playFlip()
    }
    scrollToBottom()
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

onMounted(async () => {
  // P8-2：空闲瞌睡——活动重置计时（瞌睡本身即低动效，不受动画偏好影响）
  _onPointer = (e) => onActivity(e)
  _onKey = (e) => onActivity(e)
  window.addEventListener('pointerdown', _onPointer, { passive: true })
  window.addEventListener('keydown', _onKey, { passive: true })
  onActivity()

  await chatStore.fetchSessions()
  await documentStore.fetchDocuments()

  await loadPersonas()

  if (documentStore.documents.length > 0) {
    selectedDocs.value = documentStore.documents
      .filter(d => d.status === 'ready')
      .slice(0, 1)
      .map(d => d.id)
  }

  const contextQuery = route.query.context
  const docId = route.query.docId

  if (docId && !selectedDocs.value.includes(docId as string)) {
    selectedDocs.value = [docId as string]
  }

  if (contextQuery) {
    await handleSend(contextQuery as string)
  }

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
.prose .source-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.25rem;
  height: 1.25rem;
  padding: 0 0.25rem;
  margin-left: 0.125rem;
  margin-right: 0.125rem;
  font-size: 0.625rem;
  font-weight: 600;
  color: var(--text-inverse);
  background: var(--gradient-brand);
  border-radius: 9999px;
  cursor: pointer;
  vertical-align: super;
  transition: all 0.2s ease;
}
.prose .source-badge:hover {
  transform: scale(1.1);
  box-shadow: 0 2px 8px color-mix(in srgb, var(--color-brand-from) 40%, transparent);
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
