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

          <!-- 右：真实组件预览（小巧紧凑固定高度，与之前高度一致，内容增多时自然向上顶出并支持滑动） -->
          <div ref="heroPreview" class="card !p-4 lg:!p-5 shadow-lg hidden md:flex flex-col h-[290px] hero-float w-full max-w-[460px]" aria-hidden="true">
            <!-- 头部固定栏 -->
            <div class="flex items-center justify-between px-2 pb-3 border-b border-[var(--border-default)] flex-shrink-0">
              <div class="flex items-center gap-2">
                <CopilotBotAvatar
                  class="bot-avatar-flip"
                  :size="24"
                  :mood="previewBotMood"
                  :expression="previewBotExpr"
                />
                <span class="text-xs font-semibold text-[var(--text-primary)]">Study Copilot</span>
                <span class="text-[10px] px-1.5 py-0.5 rounded bg-[var(--bg-tertiary)] text-[var(--text-muted)]">实时演示</span>
              </div>
              <span class="text-[11px] text-[var(--text-muted)] flex items-center gap-1">
                <span class="w-1.5 h-1.5 rounded-full bg-[var(--color-primary)] animate-pulse"></span>
                {{ previewPhaseLabel }}
              </span>
            </div>

            <!-- 可滑动消息内容区（固定高度，内容增长自动将上方消息往上顶） -->
            <div ref="previewScrollRef" class="flex-1 overflow-y-auto py-3 space-y-3 pr-1 text-xs preview-scroll-body">
              <!-- 用户提问气泡（完全对齐 ChatMessageItem 用户消息样式） -->
              <div class="flex justify-end">
                <div class="text-xs leading-relaxed text-[var(--text-primary)] px-3.5 py-2 rounded-lg rounded-tr-sm bg-[var(--bg-hover)] border border-[var(--border-default)] max-w-[85%] shadow-sm">
                  {{ currentDemoQuestion }}
                </div>
              </div>

              <!-- 助手回答区域（对齐 ChatMessageItem 结构：Avatar + 思考折叠 + 流式 Markdown 正文 + 来源胶囊） -->
              <div class="msg-enter">
                <div class="flex items-center gap-2 mb-1.5">
                  <CopilotBotAvatar
                    class="bot-avatar-flip"
                    :size="28"
                    :mood="previewBotMood"
                    :expression="previewBotExpr"
                    :is-streaming="previewState === 'thinking' || previewState === 'streaming'"
                  />
                  <span class="text-xs font-medium text-[var(--text-primary)]">Study Copilot</span>
                </div>

                <div class="pl-7 min-w-0">
                  <!-- 思考状态 1：等待首 token 脉冲小圆点 -->
                  <div v-if="previewState === 'thinking' && previewThinkingSteps.length === 0" class="flex items-center gap-1.5 py-1.5" aria-label="思考中">
                    <span class="thinking-dot"></span>
                    <span class="thinking-dot" style="animation-delay: 0.15s"></span>
                    <span class="thinking-dot" style="animation-delay: 0.3s"></span>
                  </div>

                  <!-- 思考状态 2：Agentic RAG 结构化思考步骤 -->
                  <div
                    v-else-if="previewThinkingSteps.length > 0"
                    class="thinking-section mb-2.5 p-2 rounded-md bg-[var(--bg-tertiary)]/60 border border-[var(--border-default)] text-[11px]"
                  >
                    <div class="text-xs text-[var(--text-secondary)] font-medium flex items-center gap-1 mb-1.5">
                      <el-icon class="w-3 h-3 text-[var(--color-primary)]"><MagicStick /></el-icon>
                      <span>Agentic 思考过程 ({{ previewThinkingSteps.length }} 步)</span>
                    </div>
                    <div
                      v-for="(t, ti) in previewThinkingSteps"
                      :key="ti"
                      class="flex items-start gap-1.5 py-0.5 text-[11px] text-[var(--text-muted)]"
                    >
                      <span class="font-medium text-[var(--color-primary)] flex-shrink-0">{{ ti + 1 }}.</span>
                      <span class="leading-relaxed">{{ t }}</span>
                    </div>
                  </div>

                  <!-- 流式打字机正文（带呼吸光标） -->
                  <div v-if="previewDisplayedText" class="text-xs leading-[1.75] text-[var(--text-primary)]">
                    <span>{{ previewDisplayedText }}</span>
                    <span v-if="previewState === 'streaming'" class="stream-caret" aria-hidden="true"></span>
                  </div>

                  <!-- 来源胶囊（参考来源） -->
                  <div
                    v-if="previewSources.length > 0 && previewState === 'completed'"
                    class="mt-3 pt-2 border-t border-[var(--border-default)] flex flex-wrap items-center gap-1.5"
                  >
                    <span class="text-[10px] text-[var(--text-muted)] mr-1">参考来源:</span>
                    <div
                      v-for="src in previewSources"
                      :key="src.idx"
                      class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-[var(--bg-tertiary)] border border-[var(--border-default)] text-[10px] text-[var(--text-secondary)]"
                    >
                      <span class="w-3.5 h-3.5 rounded-full bg-[var(--color-primary)] text-[var(--text-inverse)] text-[9px] flex items-center justify-center font-medium">
                        {{ src.idx }}
                      </span>
                      <span class="truncate max-w-[100px]">{{ src.title }}</span>
                      <span class="text-[var(--text-muted)]">P{{ src.page }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 底部固定栏（始终钉在底部） -->
            <div class="pt-2.5 flex items-center justify-between text-[10px] text-[var(--text-muted)] border-t border-[var(--border-default)] flex-shrink-0">
              <span>RAG 检索增强 + 自适应反思</span>
              <router-link to="/chat" class="text-[var(--color-primary)] hover:underline flex items-center gap-0.5">
                体验完整对话
                <el-icon class="w-2.5 h-2.5"><ArrowRight /></el-icon>
              </router-link>
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

    <!-- Features Section (不等宽交错长条双排 · 持续慢速无缝滚动) -->
    <section ref="featuresSection" class="py-12 bg-[var(--bg-secondary)] overflow-hidden">
      <div class="max-w-6xl mx-auto px-6 mb-6">
        <div class="flex items-center justify-between">
          <h2 class="text-xl font-semibold text-[var(--text-primary)]">功能介绍</h2>
        </div>
      </div>

      <!-- 持续无缝滚动容器（左右两端带柔和渐变遮罩） -->
      <div
        class="relative w-full overflow-hidden marquee-wrapper py-2"
        @mouseenter="isHovered = true"
        @mouseleave="isHovered = false"
      >
        <!-- 左侧边缘渐变遮罩 -->
        <div class="pointer-events-none absolute left-0 top-0 bottom-0 w-16 sm:w-28 bg-gradient-to-r from-[var(--bg-secondary)] to-transparent z-10"></div>
        <!-- 右侧边缘渐变遮罩 -->
        <div class="pointer-events-none absolute right-0 top-0 bottom-0 w-16 sm:w-28 bg-gradient-to-l from-[var(--bg-secondary)] to-transparent z-10"></div>

        <div class="flex flex-col gap-5">
          <!-- 第一排：宽卡与窄卡交替（380px / 280px），向左慢速平滑滚动 -->
          <div class="marquee-track marquee-row-1 flex gap-5 w-max">
            <div
              v-for="(item, idx) in marqueeRow1"
              :key="`r1-${idx}`"
              @click="router.push(item.link)"
              :class="[
                item.widthClass,
                'card p-5 hover:border-[var(--color-primary)] hover:shadow-md transition-all cursor-pointer group flex flex-col justify-between h-[168px] flex-shrink-0'
              ]"
            >
              <div>
                <div class="flex items-start gap-3.5 mb-2">
                  <div class="w-11 h-11 bg-[var(--bg-tertiary)] dark:bg-[var(--text-secondary)]/10 rounded-xl flex items-center justify-center flex-shrink-0 group-hover:scale-105 transition-transform text-[var(--color-primary)]">
                    <el-icon class="w-5 h-5"><component :is="item.icon" /></el-icon>
                  </div>
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center justify-between mb-1">
                      <h3 class="text-sm font-semibold text-[var(--text-primary)] group-hover:text-[var(--color-primary)] transition-colors truncate">
                        {{ item.title }}
                      </h3>
                      <span class="text-[11px] px-2 py-0.5 rounded-full bg-[var(--bg-tertiary)] text-[var(--text-secondary)] font-medium flex-shrink-0 ml-2">
                        {{ item.tag }}
                      </span>
                    </div>
                    <p class="text-[var(--text-secondary)] text-xs leading-relaxed line-clamp-2">
                      {{ item.desc }}
                    </p>
                  </div>
                </div>
              </div>
              <div class="pt-2 flex items-center justify-end text-xs text-[var(--text-muted)] group-hover:text-[var(--color-primary)] transition-colors">
                <span class="mr-1">进入功能</span>
                <el-icon class="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform"><ArrowRight /></el-icon>
              </div>
            </div>
          </div>

          <!-- 第二排：窄卡与宽卡交替（280px / 380px），错落对应第一排，持续向左滚动 -->
          <div class="marquee-track marquee-row-2 flex gap-5 w-max">
            <div
              v-for="(item, idx) in marqueeRow2"
              :key="`r2-${idx}`"
              @click="router.push(item.link)"
              :class="[
                item.widthClass,
                'card p-5 hover:border-[var(--color-primary)] hover:shadow-md transition-all cursor-pointer group flex flex-col justify-between h-[168px] flex-shrink-0'
              ]"
            >
              <div>
                <div class="flex items-start gap-3.5 mb-2">
                  <div class="w-11 h-11 bg-[var(--bg-tertiary)] dark:bg-[var(--text-secondary)]/10 rounded-xl flex items-center justify-center flex-shrink-0 group-hover:scale-105 transition-transform text-[var(--color-primary)]">
                    <el-icon class="w-5 h-5"><component :is="item.icon" /></el-icon>
                  </div>
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center justify-between mb-1">
                      <h3 class="text-sm font-semibold text-[var(--text-primary)] group-hover:text-[var(--color-primary)] transition-colors truncate">
                        {{ item.title }}
                      </h3>
                      <span class="text-[11px] px-2 py-0.5 rounded-full bg-[var(--bg-tertiary)] text-[var(--text-secondary)] font-medium flex-shrink-0 ml-2">
                        {{ item.tag }}
                      </span>
                    </div>
                    <p class="text-[var(--text-secondary)] text-xs leading-relaxed line-clamp-2">
                      {{ item.desc }}
                    </p>
                  </div>
                </div>
              </div>
              <div class="pt-2 flex items-center justify-end text-xs text-[var(--text-muted)] group-hover:text-[var(--color-primary)] transition-colors">
                <span class="mr-1">进入功能</span>
                <el-icon class="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform"><ArrowRight /></el-icon>
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
import { ref, onMounted, onUnmounted, computed, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useDocumentStore } from '../stores/document'
import { useChatStore } from '../stores/chat'
import {
  Upload,
  ChatDotSquare,
  DocumentChecked,
  Tickets,
  MagicStick,
  TrendCharts,
  ArrowRight,
  EditPen,
  Switch,
  Reading,
  Link,
  Promotion
} from '@/components/icons'
import { formatDayLabel } from '../composables/useFormat'
import { useReducedMotion } from '../composables/useReducedMotion'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import CopilotBotAvatar, { type BotMood } from '@/components/CopilotBotAvatar.vue'
import type { ExpressionId } from '@/bot/expressions'

gsap.registerPlugin(ScrollTrigger)

const router = useRouter()
const documentStore = useDocumentStore()
const chatStore = useChatStore()
// P1-1：GSAP 动画入口统一降级（prefers-reduced-motion）
const { prefersReduced } = useReducedMotion()

// 首页右侧真实对话流式演示状态
type DemoPhase = 'idle' | 'user_ask' | 'thinking' | 'streaming' | 'completed'

const demoScript = [
  // 剧本 1：Agentic RAG 学术与论文检索
  {
    question: '这篇论文的核心结论是什么？',
    thinkingSteps: [
      '解析用户查询意图，识别核心观点抽取任务',
      '从知识库检索 4 篇相关片段，混合检索融合度 0.94',
      '综合原文第 12 页实验结果，完成结论凝练与自我校验'
    ],
    fullAnswer: '核心结论有三点：第一，在多模态 Agentic RAG 框架下，引入动态反思机制可使事实准确率提升 28%；第二，混合检索融合 BM25 与语义向量在专业技术文档上表现出显著的鲁棒性；第三，持久化异步队列有效保障了百万级 Token 场景的吞吐稳定性。',
    sources: [
      { idx: 1, title: 'agentic_rag_paper.pdf', page: 12 },
      { idx: 2, title: 'benchmark_eval.pdf', page: 4 }
    ]
  },
  // 剧本 2：课程空间与考试复习闭环
  {
    question: '如何在这套系统里快速为明天的考试复习？',
    thinkingSteps: [
      '路由至学习巩固模块，定位考点提取模型',
      '匹配相关课程空间的重点笔记与高频错题'
    ],
    fullAnswer: '推荐三步快速巩固：首先在【课程空间】上传课件一键提取考点大纲；然后在【智能出题】生成 10 道针对性选择题模拟全真考试；最后查看【错题雷达】，系统会自动为你规划易错薄弱点的定向补强。',
    sources: [
      { idx: 1, title: '复习指南.docx', page: 3 },
      { idx: 2, title: '课程大纲.pdf', page: 1 }
    ]
  },
  // 剧本 3：多维内容转换（思维导图与记忆卡片）
  {
    question: '把第三章的分布式共识算法整理成记忆卡片和脑图。',
    thinkingSteps: [
      '识别内容变形需求：格式化为卡片组与思维导图节点',
      '精确抽取 Raft 与 PBFT 的核心选举与日志复制机制',
      '完成结构化分级与概念对照校验'
    ],
    fullAnswer: '已为你提炼出 2 张高频记忆卡片与导图分支：\n1. 【Raft 共识机制】：Leader 选举、日志复制（Log Replication）与安全性不变量；\n2. 【拜占庭容错 PBFT】：三阶段协议（Pre-Prepare, Prepare, Commit），容忍不超过 1/3 的恶意节点。点击右上角【内容转换】可一键导出交互式脑图。',
    sources: [
      { idx: 1, title: '分布式系统架构.pdf', page: 45 },
      { idx: 2, title: '共识算法讲义.pptx', page: 18 }
    ]
  },
  // 剧本 4：笔记沉淀与全局向量语义搜索
  {
    question: '我之前记过关于微服务服务熔断的笔记在哪里？',
    thinkingSteps: [
      '执行笔记库向量嵌入与语义索引匹对',
      '匹配到 2 篇关联度 > 0.88 的历史随手记与课堂摘录'
    ],
    fullAnswer: '已为你找到 2 条相关笔记：\n• 《分布式容错设计》第 4 节：记录了 Sentinel 与 Hystrix 滑动窗口熔断对比，以及慢调用比例阈值配置；\n• 对话摘录《Spring Cloud 实践》：重点强调了熔断降级对下游核心链路的兜底保护。已为你标注原文锚点。',
    sources: [
      { idx: 1, title: '我的知识库/分布式笔记.md', page: 1 },
      { idx: 2, title: '微服务架构课堂记录.txt', page: 2 }
    ]
  },
  // 剧本 5：AI 错题分析与学情雷达诊断
  {
    question: '根据最近几次测验，我最薄弱的知识点是什么？',
    thinkingSteps: [
      '聚合历史测验答题卡，计算各知识域正确率均值',
      '定位低分模块：动态规划（42%）与网络协议握手（50%）',
      '自适应生成针对性专项复习与补救题目建议'
    ],
    fullAnswer: '学情诊断雷达显示，你当前最需加强的模块是【动态规划状态转移方程】（正确率 42%）与【TCP 四次挥手 TIME_WAIT 状态机】（正确率 50%）。建议通过系统生成的专项强化练习题进行针对性突破！',
    sources: [
      { idx: 1, title: '计算机网络全真练习卷.pdf', page: 8 },
      { idx: 2, title: '算法与数据结构期末小测.pdf', page: 3 }
    ]
  }
]

const demoIndex = ref(0)
const previewState = ref<DemoPhase>('idle')
const currentDemoQuestion = ref(demoScript[0].question)
const previewThinkingSteps = ref<string[]>([])
const previewDisplayedText = ref('')
const previewSources = ref<{ idx: number; title: string; page: number }[]>([])

const previewPhaseLabel = computed(() => {
  switch (previewState.value) {
    case 'idle': return '准备就绪'
    case 'user_ask': return '收到提问'
    case 'thinking': return 'Agentic 检索与思考中...'
    case 'streaming': return '正在流式回答...'
    case 'completed': return '回答完毕 · 来源已核验'
    default: return 'AI 问答'
  }
})

const previewBotMood = computed<BotMood>(() => {
  switch (previewState.value) {
    case 'idle': return 'idle'
    case 'user_ask': return 'acknowledge'
    case 'thinking': return 'thinking'
    case 'streaming': return 'answering'
    case 'completed': return 'done'
    default: return 'idle'
  }
})

const previewBotExpr = computed<ExpressionId>(() => {
  switch (previewState.value) {
    case 'idle': return 'neutre'
    case 'user_ask': return 'attentif'
    case 'thinking': return 'mefiant'
    case 'streaming': return 'attentif'
    case 'completed': return 'heureux'
    default: return 'neutre'
  }
})

let demoLoopTimer: ReturnType<typeof setTimeout> | null = null

async function runHeroDemoCycle(): Promise<void> {
  const currentDemo = demoScript[demoIndex.value]
  currentDemoQuestion.value = currentDemo.question
  previewThinkingSteps.value = []
  previewDisplayedText.value = ''
  previewSources.value = []
  await nextTick()
  scrollPreviewToBottom()

  // 1. 用户提问阶段 (原 0.9s -> 3 倍延长至 2.7s，供用户从容读题)
  previewState.value = 'user_ask'
  await waitMs(2700)

  // 2. 思考阶段：先显示脉冲小圆点，再逐步输出 Agentic 思考步骤 (原 ~2.5s -> 3 倍延长至 ~7.5s)
  previewState.value = 'thinking'
  for (let i = 0; i < currentDemo.thinkingSteps.length; i++) {
    await waitMs(1800)
    previewThinkingSteps.value.push(currentDemo.thinkingSteps[i])
    await nextTick()
    scrollPreviewToBottom()
  }
  await waitMs(1500)

  // 3. 流式打字输出阶段：从容逐字打出完整回答 (原 35ms -> 70ms，平缓吐字并将上方内容自然往上顶)
  previewState.value = 'streaming'
  const fullText = currentDemo.fullAnswer
  for (let i = 0; i <= fullText.length; i += 2) {
    previewDisplayedText.value = fullText.slice(0, i)
    await nextTick()
    scrollPreviewToBottom()
    await waitMs(70)
  }
  previewDisplayedText.value = fullText
  await nextTick()
  scrollPreviewToBottom()

  // 4. 完成阶段：挂载参考来源胶囊，Bot 切换为愉悦完成表情 (原 4.5s -> 3 倍延长至 13.5s，充分阅读与体验手动滑动)
  previewState.value = 'completed'
  previewSources.value = currentDemo.sources
  await nextTick()
  scrollPreviewToBottom()
  await waitMs(13500)

  // 5. 切换到下一个演示剧本并循环
  demoIndex.value = (demoIndex.value + 1) % demoScript.length
  runHeroDemoCycle()
}

function waitMs(ms: number): Promise<void> {
  return new Promise(resolve => {
    demoLoopTimer = setTimeout(resolve, ms)
  })
}

function stopHeroDemo(): void {
  if (demoLoopTimer) {
    clearTimeout(demoLoopTimer)
    demoLoopTimer = null
  }
}

// Template refs
const homeContainer = ref<HTMLElement | null>(null)
const heroTitle = ref<HTMLElement | null>(null)
const heroSubtitle = ref<HTMLElement | null>(null)
const heroButtons = ref<HTMLElement | null>(null)
const quickActions = ref<HTMLElement | null>(null)
const featuresSection = ref<HTMLElement | null>(null)
const heroPreview = ref<HTMLElement | null>(null)
const previewScrollRef = ref<HTMLElement | null>(null)

function scrollPreviewToBottom(): void {
  if (previewScrollRef.value) {
    previewScrollRef.value.scrollTop = previewScrollRef.value.scrollHeight
  }
}

let ctx: gsap.Context | null = null
let refreshTimer: ReturnType<typeof setTimeout> | null = null

const recentDocs = computed(() => documentStore.documents.slice(0, 5))
const recentChats = computed(() => chatStore.sessions.slice(0, 5))

// 当最近文档或最近对话数据加载完成后，页面高度发生变化，主动重算 ScrollTrigger
watch([recentDocs, recentChats], async () => {
  await nextTick()
  ScrollTrigger.refresh()
})

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

/**
 * Study Copilot v2 全量特色功能清单
 * 组织为上下两排连续长条，每排长宽卡片交替排列：
 * - 第一排：宽卡(380px)与窄卡(280px)交替
 * - 第二排：窄卡(280px)与宽卡(380px)交替
 * 卡片高度完全统一（h-[168px]），不等宽交错，持续慢速无缝滚动。
 */
interface FeatureCardItem {
  title: string
  desc: string
  tag: string
  icon: any
  link: string
  widthClass: string
}

const rawRow1Features: FeatureCardItem[] = [
  {
    title: '智能文档高保真解析',
    desc: '基于 Docling 多模态引擎，深度提取 PDF、DOCX、PPTX 中的复杂表格与层级结构，精准构建知识库。',
    tag: '文档中枢',
    icon: Tickets,
    link: '/upload',
    widthClass: 'w-[360px] sm:w-[400px]'
  },
  {
    title: 'AI 智能自动出题',
    desc: '一键提取文档考点生成选择题与简答题，练习与全真考试两种模式随时切换。',
    tag: '学习巩固',
    icon: DocumentChecked,
    link: '/quiz',
    widthClass: 'w-[270px] sm:w-[300px]'
  },
  {
    title: '错题分析与学情雷达',
    desc: '自动记录全量练习，AI 诊断弱项知识点分布与正确率走势，针对薄弱环节定点突击。',
    tag: '学情诊断',
    icon: TrendCharts,
    link: '/analysis',
    widthClass: 'w-[360px] sm:w-[400px]'
  },
  {
    title: '网页 URL 快速导入',
    desc: '粘贴任意技术文档或网页链接，自动化过滤杂质广告与抓取核心正文，秒级入库入脑。',
    tag: '全网采集',
    icon: Link,
    link: '/upload',
    widthClass: 'w-[270px] sm:w-[300px]'
  },
  {
    title: '多端凭证与模型自选',
    desc: 'Fernet 高强度加密存储 API Key，支持 OpenAI、Anthropic、Gemini 及主流兼容大模型自由切换。',
    tag: '安全灵活',
    icon: Tickets,
    link: '/settings',
    widthClass: 'w-[360px] sm:w-[400px]'
  },
  {
    title: '课程主题空间体系化管理',
    desc: '按课程空间体系化收纳文档与笔记，支持一键由多篇参考资料自动生成章节课程大纲。',
    tag: '结构归档',
    icon: Reading,
    link: '/courses',
    widthClass: 'w-[270px] sm:w-[300px]'
  }
]

const rawRow2Features: FeatureCardItem[] = [
  {
    title: 'Agentic RAG 检索生成',
    desc: '融合查询路由、自适应检索与答案自我反思，每个论断精准附带原文溯源引用。',
    tag: '核心引擎',
    icon: MagicStick,
    link: '/chat',
    widthClass: 'w-[270px] sm:w-[300px]'
  },
  {
    title: '多维内容转换 (8 大形态)',
    desc: '支持摘要、核心要点、大纲、记忆卡片、思维导图、问答集、专业翻译与通俗解释等形态一键变形。',
    tag: '深度吸收',
    icon: Switch,
    link: '/documents',
    widthClass: 'w-[360px] sm:w-[400px]'
  },
  {
    title: '智能笔记与语义检索',
    desc: '支持随手记与 AI 对话一键沉淀，内置向量语义索引，模糊语义随心搜寻。',
    tag: '知识沉淀',
    icon: EditPen,
    link: '/notes',
    widthClass: 'w-[270px] sm:w-[300px]'
  },
  {
    title: '异步持久化任务队列',
    desc: '复杂解析切块与出题任务后台调度运行，支持看门狗超时监控与重启自动找回孤儿任务。',
    tag: '高效异步',
    icon: Promotion,
    link: '/tasks',
    widthClass: 'w-[360px] sm:w-[400px]'
  },
  {
    title: '混合检索与智能路由',
    desc: '向量语义结合关键词（BM25+Jieba），通过 RRF 倒数排名融合算法精准命中。',
    tag: '双轨检索',
    icon: MagicStick,
    link: '/chat',
    widthClass: 'w-[270px] sm:w-[300px]'
  },
  {
    title: '语音朗读与多模态交互',
    desc: '集成 Edge TTS 高自然度语音合成，支持回答与重点笔记即时朗读，释放双眼随时听学。',
    tag: '多模交互',
    icon: Reading,
    link: '/notes',
    widthClass: 'w-[360px] sm:w-[400px]'
  }
]

// 重复拼接以形成首尾无缝衔接的持续跑马灯长条
const marqueeRow1 = [...rawRow1Features, ...rawRow1Features]
const marqueeRow2 = [...rawRow2Features, ...rawRow2Features]

// 鼠标悬停控制（用于暂停或调整滚动状态）
const isHovered = ref(false)

// P2-1：formatDate 由 useFormat.formatDayLabel 替换（原为 4 处平行实现之一）
const formatDate = formatDayLabel

function goToChat(docId: string): void {
  router.push({ path: '/chat', query: { docId } })
}

onMounted(async () => {
  // 数据请求 fire-and-forget：失败静默，列表区展示既有空态
  documentStore.fetchDocuments().catch(() => {})
  chatStore.fetchSessions().catch(() => {})

  // 等待 Vue DOM 挂载和页面路由过渡初态
  await nextTick()
  if (!homeContainer.value) return
  if (prefersReduced.value) return

  ctx = gsap.context(() => {
    // 1. Hero 区域文字与按钮依次渐入
    if (heroTitle.value) {
      gsap.from(heroTitle.value, {
        y: 40,
        opacity: 0,
        duration: 0.8,
        ease: 'power2.out'
      })
    }
    if (heroSubtitle.value) {
      gsap.from(heroSubtitle.value, {
        y: 40,
        opacity: 0,
        duration: 0.8,
        delay: 0.15,
        ease: 'power2.out'
      })
    }
    if (heroButtons.value) {
      gsap.from(heroButtons.value, {
        y: 40,
        opacity: 0,
        duration: 0.8,
        delay: 0.3,
        ease: 'power2.out'
      })
    }
    if (heroPreview.value) {
      gsap.from(heroPreview.value, {
        y: 30,
        opacity: 0,
        duration: 0.8,
        delay: 0.25,
        ease: 'power2.out'
      })
    }

    // 2. 快速开始卡片：大屏或进入视口时稳定触发（fastScrollEnd 防丢帧，top 92% 避免边缘滞留）
    const quickCards = quickActions.value?.children
    if (quickCards?.length) {
      gsap.from(quickCards, {
        y: 36,
        opacity: 0,
        duration: 0.6,
        stagger: 0.08,
        ease: 'power2.out',
        scrollTrigger: {
          trigger: quickActions.value,
          start: 'top 92%',
          fastScrollEnd: true,
          once: true
        }
      })
    }

    // 3. 功能介绍板块入场显现
    if (featuresSection.value) {
      gsap.from(featuresSection.value, {
        y: 35,
        opacity: 0,
        duration: 0.7,
        ease: 'power2.out',
        scrollTrigger: {
          trigger: featuresSection.value,
          start: 'top 90%',
          fastScrollEnd: true,
          once: true
        }
      })
    }
  }, homeContainer.value)

  // 启动真实交互流式演练演示循环
  runHeroDemoCycle()

  // 立即刷新一次位置
  ScrollTrigger.refresh()

  // 延迟 220ms 再次刷新：等待 App.vue 中的 <Transition name="page"> 0.2s 页面路由过渡完全结束
  // 彻底避免从长页面跳转回首页时，因历史滚动位移或路由过渡尺寸计算偏差导致的触发点脱靶
  refreshTimer = setTimeout(() => {
    ScrollTrigger.refresh()
  }, 250)
})

onUnmounted(() => {
  stopHeroDemo()
  if (refreshTimer) clearTimeout(refreshTimer)
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

/* 跑马灯滚动条隐藏与触控平滑 */
.no-scrollbar::-webkit-scrollbar {
  display: none;
}
.no-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

/* 
 * 跑马灯长条无缝持续慢速横向滚动动画 
 * 两排以 50s / 45s 平滑持续平移 -50%（因为两段完全相同，-50% 刚好无缝循环）
 * 鼠标悬停暂停动画 (paused)，移出继续流动
 */
.marquee-track {
  will-change: transform;
}

.marquee-row-1 {
  animation: marquee-scroll 48s linear infinite;
}

.marquee-row-2 {
  animation: marquee-scroll 44s linear infinite;
}

.marquee-wrapper:hover .marquee-track {
  animation-play-state: paused;
}

@keyframes marquee-scroll {
  0% {
    transform: translateX(0);
  }
  100% {
    transform: translateX(-50%);
  }
}

@media (prefers-reduced-motion: reduce) {
  .marquee-row-1,
  .marquee-row-2 {
    animation: none;
  }
}

/* 思考中三点脉冲 */
.thinking-dot {
  width: 5px;
  height: 5px;
  border-radius: 9999px;
  background: var(--text-muted);
  animation: dot-pulse 1.2s ease-in-out infinite;
}
@keyframes dot-pulse {
  0%, 100% { opacity: 0.3; transform: translateY(0); }
  50% { opacity: 1; transform: translateY(-2.5px); }
}

/* 流式打字机光标：品牌色竖条呼吸 */
.stream-caret {
  display: inline-block;
  width: 2px;
  height: 1.1em;
  margin-left: 2px;
  vertical-align: -2px;
  background: var(--color-primary);
  animation: caret-blink 0.9s steps(1) infinite;
}
@keyframes caret-blink {
  0%, 55% { opacity: 1; }
  56%, 100% { opacity: 0; }
}

@media (prefers-reduced-motion: reduce) {
  .thinking-dot {
    animation: none;
  }
  .stream-caret {
    animation: none;
    opacity: 1;
  }
}

/* 首页预览框内部精致可滑动滚动条 */
.preview-scroll-body {
  scroll-behavior: smooth;
  scrollbar-width: thin;
  scrollbar-color: var(--border-hover) transparent;
}
.preview-scroll-body::-webkit-scrollbar {
  width: 4px;
}
.preview-scroll-body::-webkit-scrollbar-track {
  background: transparent;
}
.preview-scroll-body::-webkit-scrollbar-thumb {
  background: var(--border-hover);
  border-radius: 9999px;
}
.preview-scroll-body::-webkit-scrollbar-thumb:hover {
  background: var(--text-muted);
}
</style>