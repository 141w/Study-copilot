<template>
  <div ref="homeContainer" class="min-h-screen bg-[var(--bg-primary)]">
    <!-- Hero Section（P2-2：分栏布局 + 真实组件预览，§4.3/§4.8） -->
    <section class="relative overflow-hidden">
      <div class="absolute inset-0 pastel-gradient opacity-50"></div>
      <div class="relative max-w-6xl mx-auto px-6 py-16 lg:py-20">
        <div class="grid lg:grid-cols-2 gap-10 lg:gap-8 items-center">
          <!-- 左：文案（≤4 文本元素：标题/副文案/CTA，§4.7） -->
          <div>
            <!-- 精修（批次3）：移除负字距——对全角 CJK 字形有害；
                 拉丁品牌名单独保留紧凑字距 -->
            <h1 ref="heroTitle" class="text-4xl md:text-5xl font-semibold text-[var(--text-primary)] mb-4 leading-[1.2]">
              把学习资料变成<br/>
              <span class="gradient-text letter-spacing-tight">Study Copilot</span> 知识库
            </h1>
            <p ref="heroSubtitle" class="text-lg text-[var(--text-secondary)] mb-8 max-w-xl leading-[1.8]">
              上传文档，即刻获得带来源引用的问答、练习题与错题分析。
            </p>
            <div ref="heroButtons" class="flex gap-4">
              <router-link to="/upload"><el-button type="primary" size="large">上传文档</el-button></router-link>
              <router-link to="/chat"><el-button size="large">开始问答</el-button></router-link>
            </div>
          </div>

          <!-- 右：真实组件预览（§4.8 real component preview，非 div 假截图）。
               复刻 ChatView 消息结构：用户气泡 + 助手回答 + 来源胶囊 -->
          <div ref="heroPreview" class="card !p-4 lg:!p-5 shadow-lg hidden md:block hero-float" aria-hidden="true">
            <div class="flex items-center gap-2 px-2 pb-3 border-b border-[var(--border-default)]">
              <div class="w-6 h-6 rounded-full bg-gradient-to-br from-[var(--color-brand-from)] to-[var(--color-brand-to)]"></div>
              <span class="text-xs font-medium text-[var(--text-secondary)]">AI 问答</span>
            </div>
            <div class="pt-3 space-y-3">
              <div class="flex justify-end">
                <div class="text-xs text-[var(--text-inverse)] px-3 py-2 rounded-lg rounded-tr-sm bg-[var(--color-primary)] max-w-[75%]">
                  这篇论文的核心结论是什么？
                </div>
              </div>
              <div class="flex gap-2">
                <div class="w-6 h-6 rounded-full bg-[var(--bg-tertiary)] flex-shrink-0 flex items-center justify-center">
                  <el-icon class="w-3.5 h-3.5 text-[var(--text-secondary)]"><ChatDotSquare /></el-icon>
                </div>
                <div class="text-xs text-[var(--text-primary)] leading-[1.75] bg-[var(--bg-secondary)] rounded-lg rounded-tl-sm px-3 py-2 max-w-[85%]">
                  核心结论有三点：第一……第二……第三……
                  <div class="flex flex-wrap gap-1 mt-2">
                    <span class="text-[10px] px-1.5 py-0.5 rounded-full bg-[var(--bg-tertiary)] border border-[var(--border-default)] text-[var(--text-secondary)]">1 论文.pdf</span>
                    <span class="text-[10px] px-1.5 py-0.5 rounded-full bg-[var(--bg-tertiary)] border border-[var(--border-default)] text-[var(--text-secondary)]">2 P12</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 三步流程条（P2-2：替代四等分卡片墙，消除 hero/卡片/空态三处同意图 CTA） -->
    <section class="py-10">
      <div class="max-w-6xl mx-auto px-6">
        <h2 class="text-xl font-semibold text-[var(--text-primary)] mb-6">快速开始</h2>
        <div ref="quickActions" class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <router-link
            v-for="step in steps"
            :key="step.to"
            :to="step.to"
            class="card p-5 hover:border-[var(--color-primary)] transition-colors group flex items-center gap-4"
          >
            <div
              class="w-11 h-11 rounded-lg flex items-center justify-center flex-shrink-0 transition-colors"
              :class="step.bgClass"
            >
              <el-icon class="w-5 h-5" :class="step.iconClass"><component :is="step.icon" /></el-icon>
            </div>
            <div class="min-w-0">
              <h3 class="font-semibold text-[var(--text-primary)]">{{ step.title }}</h3>
              <p class="text-sm text-[var(--text-muted)] truncate">{{ step.desc }}</p>
            </div>
            <el-icon class="w-4 h-4 ml-auto text-[var(--text-muted)] group-hover:text-[var(--color-primary)] transition-colors flex-shrink-0"><ArrowRight /></el-icon>
          </router-link>
        </div>
      </div>
    </section>

    <!-- Features Introduction -->
    <section class="py-10 bg-[var(--bg-secondary)]">
      <div class="max-w-6xl mx-auto px-6">
        <h2 class="text-xl font-semibold text-[var(--text-primary)] mb-6">功能介绍</h2>

        <!-- P2-2：不等宽双列错落（md:grid-cols-5 交替 3/2），打破等分卡片墙 -->
        <div ref="featureCards" class="grid grid-cols-1 md:grid-cols-5 gap-6">
          <!-- Feature 1 -->
          <div class="card p-6 md:col-span-3">
            <div class="flex items-start gap-4">
              <div class="w-14 h-14 bg-[var(--bg-tertiary)] dark:bg-[var(--text-secondary)]/10 rounded-xl flex items-center justify-center flex-shrink-0">
                <el-icon class="w-7 h-7 text-[var(--text-secondary)]"><Tickets /></el-icon>
              </div>
              <div>
                <h3 class="text-lg font-semibold text-[var(--text-primary)] mb-2">智能文档解析</h3>
                <p class="text-[var(--text-secondary)] text-sm leading-relaxed">
                  上传 PDF、DOCX、PPTX，自动提取文本、表格与结构，构建可检索的向量知识库。
                </p>
              </div>
            </div>
          </div>

          <!-- Feature 2 -->
          <div class="card p-6 md:col-span-2">
            <div class="flex items-start gap-4">
              <div class="w-14 h-14 bg-[var(--bg-tertiary)] dark:bg-[var(--text-secondary)]/10 rounded-xl flex items-center justify-center flex-shrink-0">
                <el-icon class="w-7 h-7 text-[var(--text-secondary)]"><MagicStick /></el-icon>
              </div>
              <div>
                <h3 class="text-lg font-semibold text-[var(--text-primary)] mb-2">RAG 智能问答</h3>
                <p class="text-[var(--text-secondary)] text-sm leading-relaxed">
                  答案来自你的文档，每个结论都带来源引用，可一键跳回原文。
                </p>
              </div>
            </div>
          </div>

          <!-- Feature 3 -->
          <div class="card p-6 md:col-span-2">
            <div class="flex items-start gap-4">
              <div class="w-14 h-14 bg-[var(--bg-tertiary)] dark:bg-[var(--text-secondary)]/10 rounded-xl flex items-center justify-center flex-shrink-0">
                <el-icon class="w-7 h-7 text-[var(--text-secondary)]"><DocumentChecked /></el-icon>
              </div>
              <div>
                <h3 class="text-lg font-semibold text-[var(--text-primary)] mb-2">AI 自动出题</h3>
                <p class="text-[var(--text-secondary)] text-sm leading-relaxed">
                  从任意文档生成选择题与简答题，练习与考试两种模式随时切换。
                </p>
              </div>
            </div>
          </div>

          <!-- Feature 4 -->
          <div class="card p-6 md:col-span-3">
            <div class="flex items-start gap-4">
              <div class="w-14 h-14 bg-[var(--bg-tertiary)] dark:bg-[var(--text-secondary)]/10 rounded-xl flex items-center justify-center flex-shrink-0">
                <el-icon class="w-7 h-7 text-[var(--text-secondary)]"><TrendCharts /></el-icon>
              </div>
              <div>
                <h3 class="text-lg font-semibold text-[var(--text-primary)] mb-2">错题分析与学习追踪</h3>
                <p class="text-[var(--text-secondary)] text-sm leading-relaxed">
                  每次作答都被记录，薄弱知识点自动汇总，复习有的放矢。
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Recent Content -->
    <section class="py-10">
      <div class="max-w-6xl mx-auto px-6">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
          <!-- Recent Documents -->
          <div class="card">
            <div class="p-4 border-b border-[var(--border-default)] flex items-center justify-between">
              <h3 class="font-semibold text-[var(--text-primary)]">最近文档</h3>
              <router-link to="/documents" class="text-sm text-[var(--color-primary)] hover:underline">查看全部</router-link>
            </div>
            <div v-if="recentDocs.length === 0" class="p-8 text-center">
              <div class="w-16 h-16 mx-auto mb-4 bg-[var(--bg-tertiary)] rounded-full flex items-center justify-center">
                <el-icon class="w-8 h-8 text-[var(--text-muted)]"><Tickets /></el-icon>
              </div>
              <p class="text-[var(--text-muted)] mb-4">暂无文档</p>
              <router-link to="/upload" class="text-sm text-[var(--color-primary)] hover:underline">去上传</router-link>
            </div>
            <div v-else class="divide-y divide-[var(--border-default)]">
              <div v-for="doc in recentDocs" :key="doc.id" class="p-4 hover:bg-[var(--bg-hover)] cursor-pointer" @click="goToChat(doc.id)">
                <div class="flex items-center gap-3">
                  <div class="w-10 h-10 bg-[var(--bg-tertiary)] dark:bg-[var(--text-secondary)]/10 rounded-lg flex items-center justify-center flex-shrink-0">
                    <el-icon class="w-5 h-5 text-[var(--text-secondary)]"><Tickets /></el-icon>
                  </div>
                  <div class="flex-1 min-w-0">
                    <div class="text-sm font-medium text-[var(--text-primary)] truncate">{{ doc.filename }}</div>
                    <div class="text-xs text-[var(--text-muted)]">{{ doc.chunk_count || 0 }} chunks · {{ formatDate(doc.created_at) }}</div>
                  </div>
                  <span v-if="doc.status === 'ready'" class="text-xs px-2 py-1 bg-[var(--color-success-light)] text-[var(--color-success)] rounded-full">就绪</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Recent Chats -->
          <div class="card">
            <div class="p-4 border-b border-[var(--border-default)] flex items-center justify-between">
              <h3 class="font-semibold text-[var(--text-primary)]">最近对话</h3>
              <router-link to="/chat" class="text-sm text-[var(--color-primary)] hover:underline">查看全部</router-link>
            </div>
            <div v-if="recentChats.length === 0" class="p-8 text-center">
              <div class="w-16 h-16 mx-auto mb-4 bg-[var(--bg-tertiary)] rounded-full flex items-center justify-center">
                <el-icon class="w-8 h-8 text-[var(--text-muted)]"><ChatDotSquare /></el-icon>
              </div>
              <p class="text-[var(--text-muted)] mb-4">暂无对话</p>
              <router-link to="/chat" class="text-sm text-[var(--color-primary)] hover:underline">去提问</router-link>
            </div>
            <div v-else class="divide-y divide-[var(--border-default)]">
              <div v-for="chat in recentChats" :key="chat.session_id" class="p-4 hover:bg-[var(--bg-hover)] cursor-pointer" @click="router.push('/chat')">
                <div class="flex items-center gap-3">
                  <div class="w-10 h-10 bg-[var(--bg-tertiary)] dark:bg-[var(--text-secondary)]/10 rounded-lg flex items-center justify-center flex-shrink-0">
                    <el-icon class="w-5 h-5 text-[var(--text-secondary)]"><ChatDotSquare /></el-icon>
                  </div>
                  <div class="flex-1 min-w-0">
                    <div class="text-sm font-medium text-[var(--text-primary)] truncate">{{ chat.title || '新对话' }}</div>
                    <div class="text-xs text-[var(--text-muted)]">{{ formatDate(chat.created_at) }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useDocumentStore } from '../stores/document'
import { useChatStore } from '../stores/chat'
import { Upload, ChatDotSquare, DocumentChecked, Tickets, MagicStick, TrendCharts, ArrowRight } from '@/components/icons'
import { formatDayLabel } from '../composables/useFormat'
import { useReducedMotion } from '../composables/useReducedMotion'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'

gsap.registerPlugin(ScrollTrigger)

const router = useRouter()
const documentStore = useDocumentStore()
const chatStore = useChatStore()
// P1-1：GSAP 动画入口统一降级（prefers-reduced-motion）
const { prefersReduced } = useReducedMotion()

// Template refs
const homeContainer = ref<HTMLElement | null>(null)
const heroTitle = ref<HTMLElement | null>(null)
const heroSubtitle = ref<HTMLElement | null>(null)
const heroButtons = ref<HTMLElement | null>(null)
const quickActions = ref<HTMLElement | null>(null)
const featureCards = ref<HTMLElement | null>(null)
const heroPreview = ref<HTMLElement | null>(null)

let ctx: gsap.Context | null = null

const recentDocs = computed(() => documentStore.documents.slice(0, 5))
const recentChats = computed(() => chatStore.sessions.slice(0, 5))

/** P2-2：三步流程数据（动词-名词步骤名，§9.F 禁"第N步"标签；CTA 意图全页唯一） */
const steps = [
  {
    to: '/upload',
    title: '上传资料',
    desc: 'PDF、DOCX、PPTX 拖拽即传',
    icon: Upload,
    bgClass: 'bg-[var(--bg-tertiary)] group-hover:bg-[var(--bg-hover)] dark:bg-[var(--text-secondary)]/10 dark:group-hover:bg-[var(--text-secondary)]/20',
    iconClass: 'text-[var(--text-secondary)]'
  },
  {
    to: '/chat',
    title: '提问对话',
    desc: '答案带来源引用，可跳回原文',
    icon: ChatDotSquare,
    bgClass: 'bg-[var(--bg-tertiary)] group-hover:bg-[var(--bg-hover)] dark:bg-[var(--text-secondary)]/10 dark:group-hover:bg-[var(--text-secondary)]/20',
    iconClass: 'text-[var(--text-secondary)]'
  },
  {
    to: '/quiz',
    title: '做题巩固',
    desc: 'AI 出题，错题自动归档',
    icon: DocumentChecked,
    bgClass: 'bg-[var(--bg-tertiary)] group-hover:bg-[var(--bg-hover)] dark:bg-[var(--text-secondary)]/10 dark:group-hover:bg-[var(--text-secondary)]/20',
    iconClass: 'text-[var(--text-secondary)]'
  }
]

// P2-1：formatDate 由 useFormat.formatDayLabel 替换（原为 4 处平行实现之一）
const formatDate = formatDayLabel

function goToChat(docId: string): void {
  router.push({ path: '/chat', query: { docId } })
}

onMounted(async () => {
  // 批次4修复：动画注册不再被数据请求阻塞。
  // 首页是公开路由，未登录/令牌过期时 /documents 会 401，
  // 原 await Promise.all(...) 抛错导致 gsap.context 从未执行，
  // 卡片停留在 gsap.from 的 opacity:0 起始态（"动画不加载"的根因）。
  // 数据改为 fire-and-forget：失败静默，列表区展示既有空态。
  documentStore.fetchDocuments().catch(() => {})
  chatStore.fetchSessions().catch(() => {})

  // Refresh layout after async data fetch (documents/chats may shift DOM)
  await nextTick()
  if (!homeContainer.value) return
  // P1-1：减少动态偏好下跳过所有入场/滚动动画（§6.B 强制）
  if (prefersReduced.value) return
  ctx = gsap.context(() => {
    // Task 1: Hero entrance animation
    gsap.from(heroTitle.value!, {
      y: 40,
      opacity: 0,
      duration: 0.8,
      ease: 'power2.out'
    })
    gsap.from(heroSubtitle.value!, {
      y: 40,
      opacity: 0,
      duration: 0.8,
      delay: 0.2,
      ease: 'power2.out'
    })
    gsap.from(heroButtons.value!, {
      y: 40,
      opacity: 0,
      duration: 0.8,
      delay: 0.4,
      ease: 'power2.out'
    })
    // P2-2：hero 预览卡跟随入场（陈述"这是产品真实形态"的叙事层次）
    if (heroPreview.value) {
      gsap.from(heroPreview.value, {
        y: 30,
        opacity: 0,
        duration: 0.8,
        delay: 0.3,
        ease: 'power2.out'
      })
    }

    // Task 2: Quick action cards scroll reveal
    const quickCards = quickActions.value?.children
    if (quickCards?.length) {
      gsap.from(quickCards, {
        y: 40,
        opacity: 0,
        duration: 0.6,
        stagger: 0.1,
        ease: 'power2.out',
        scrollTrigger: {
          trigger: quickActions.value,
          start: 'top 85%',
          once: true
        }
      })
    }

    // Task 3: Feature cards scroll reveal
    const featureEls = featureCards.value?.children
    if (featureEls?.length) {
      gsap.from(featureEls, {
        y: 50,
        opacity: 0,
        duration: 0.6,
        stagger: 0.15,
        ease: 'power2.out',
        scrollTrigger: {
          trigger: featureCards.value,
          start: 'top 85%',
          once: true
        }
      })
    }
  }, homeContainer.value)
  // Refresh after all ScrollTrigger animations are registered
  ScrollTrigger.refresh()
})

onUnmounted(() => {
  ctx?.revert()
})
</script>

<style scoped>
/* P5-6：hero 预览卡缓慢浮动（6s 呼吸、低幅度 6px，陈述"这是活的产品"但不扰阅读）。
   与 GSAP 入场不冲突：入场 0.8s 完成后 CSS 动画接管 transform。 */
.hero-float {
  animation: hero-breathe 6s ease-in-out infinite;
}
@keyframes hero-breathe {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-6px); }
}
/* §6.B：减少动态偏好下停浮（transform 已由入场动画重置） */
@media (prefers-reduced-motion: reduce) {
  .hero-float {
    animation: none;
  }
}
</style>