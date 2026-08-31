<template>
  <div ref="homeContainer" class="min-h-screen bg-[var(--bg-primary)]">
    <!-- Hero Section -->
    <section class="relative overflow-hidden">
      <div class="absolute inset-0 pastel-gradient opacity-50"></div>
      <div class="relative max-w-6xl mx-auto px-6 py-20">
        <div class="text-center">
          <h1 ref="heroTitle" class="text-5xl font-semibold text-[var(--text-primary)] mb-6" style="letter-spacing: -0.02em">
            欢迎使用<span class="gradient-text">Study Copilot</span>
          </h1>
          <p ref="heroSubtitle" class="text-xl text-[var(--text-secondary)] mb-8 max-w-2xl mx-auto">
            您的AI学习助手<br/>
            文档解析 · 智能问答 · AI出题 · 错题分析
          </p>
          <div ref="heroButtons" class="flex gap-4 justify-center">
            <router-link to="/upload"><el-button type="primary" size="large">上传文档</el-button></router-link>
            <router-link to="/chat"><el-button size="large">开始问答</el-button></router-link>
          </div>
        </div>
      </div>
    </section>

    <!-- Quick Actions -->
    <section class="py-10">
      <div class="max-w-6xl mx-auto px-6">
        <h2 class="text-xl font-semibold text-[var(--text-primary)] mb-6">快速开始</h2>
        <div ref="quickActions" class="grid grid-cols-1 md:grid-cols-4 gap-4">
          <router-link to="/upload" class="el-card p-6 hover:border-[var(--color-primary)] border-2 transition-colors group">
            <div class="w-12 h-12 bg-[var(--color-error-light)] dark:bg-[var(--color-error)]/10 rounded-2xl flex items-center justify-center mb-4 group-hover:bg-[var(--color-error-light)] dark:group-hover:bg-[var(--color-error)]/20 transition-colors">
              <el-icon class="w-6 h-6 text-[var(--color-error)]"><Upload /></el-icon>
            </div>
            <h3 class="font-semibold text-[var(--text-primary)] mb-1">上传文档</h3>
            <p class="text-sm text-[var(--text-muted)]">上传PDF学习资料</p>
          </router-link>

          <router-link to="/documents" class="el-card p-6 hover:border-[var(--color-primary)] border-2 transition-colors group">
            <div class="w-12 h-12 bg-[var(--color-info-light)] dark:bg-[var(--color-info)]/10 rounded-2xl flex items-center justify-center mb-4 group-hover:bg-[var(--color-info-light)] dark:group-hover:bg-[var(--color-info)]/20 transition-colors">
              <el-icon class="w-6 h-6 text-[var(--color-info)]"><Document /></el-icon>
            </div>
            <h3 class="font-semibold text-[var(--text-primary)] mb-1">文档管理</h3>
            <p class="text-sm text-[var(--text-muted)]">查看已上传文档</p>
          </router-link>

          <router-link to="/chat" class="el-card p-6 hover:border-[var(--color-primary)] border-2 transition-colors group">
            <div class="w-12 h-12 bg-[var(--color-accent-light, #f3f0ff)] dark:bg-[var(--color-accent)]/10 rounded-2xl flex items-center justify-center mb-4 group-hover:bg-[var(--color-accent-light, #f3f0ff)] dark:group-hover:bg-[var(--color-accent)]/20 transition-colors">
              <el-icon class="w-6 h-6 text-[var(--color-accent)]"><ChatDotSquare /></el-icon>
            </div>
            <h3 class="font-semibold text-[var(--text-primary)] mb-1">智能问答</h3>
            <p class="text-sm text-[var(--text-muted)]">基于文档的RAG问答</p>
          </router-link>

          <router-link to="/quiz" class="el-card p-6 hover:border-[var(--color-primary)] border-2 transition-colors group">
            <div class="w-12 h-12 bg-[var(--color-success-light)] dark:bg-[var(--color-success)]/10 rounded-2xl flex items-center justify-center mb-4 group-hover:bg-[var(--color-success-light)] dark:group-hover:bg-[var(--color-success)]/20 transition-colors">
              <el-icon class="w-6 h-6 text-[var(--color-success)]"><DocumentChecked /></el-icon>
            </div>
            <h3 class="font-semibold text-[var(--text-primary)] mb-1">AI出题</h3>
            <p class="text-sm text-[var(--text-muted)]">生成练习题</p>
          </router-link>
        </div>
      </div>
    </section>

    <!-- Features Introduction -->
    <section class="py-10 bg-[var(--bg-secondary)]">
      <div class="max-w-6xl mx-auto px-6">
        <h2 class="text-xl font-semibold text-[var(--text-primary)] mb-6">功能介绍</h2>

        <div ref="featureCards" class="grid grid-cols-1 md:grid-cols-2 gap-8">
          <!-- Feature 1 -->
          <div class="el-card p-6">
            <div class="flex items-start gap-4">
              <div class="w-14 h-14 bg-[var(--color-error-light)] dark:bg-[var(--color-error)]/10 rounded-2xl flex items-center justify-center flex-shrink-0">
                <el-icon class="w-7 h-7 text-[var(--color-error)]"><Tickets /></el-icon>
              </div>
              <div>
                <h3 class="text-lg font-semibold text-[var(--text-primary)] mb-2">智能文档解析</h3>
                <p class="text-[var(--text-secondary)] text-sm leading-relaxed">
                  支持PDF文件上传，采用先进的AI技术解析文档内容。能够自动识别并提取文本、表格、结构化信息，
                  构建高效的向量知识库，让您的文档变成可检索的知识体系。
                </p>
              </div>
            </div>
          </div>

          <!-- Feature 2 -->
          <div class="el-card p-6">
            <div class="flex items-start gap-4">
              <div class="w-14 h-14 bg-[var(--color-accent-light, #f3f0ff)] dark:bg-[var(--color-accent)]/10 rounded-2xl flex items-center justify-center flex-shrink-0">
                <el-icon class="w-7 h-7 text-[var(--color-accent)]"><MagicStick /></el-icon>
              </div>
              <div>
                <h3 class="text-lg font-semibold text-[var(--text-primary)] mb-2">RAG智能问答</h3>
                <p class="text-[var(--text-secondary)] text-sm leading-relaxed">
                  基于RAG（检索增强生成）技术，从您的文档向量库中检索相关信息，结合大语言模型生成准确答案。
                  不仅提供答案，还会标注参考来源，方便您追溯原文、深入学习。
                </p>
              </div>
            </div>
          </div>

          <!-- Feature 3 -->
          <div class="el-card p-6">
            <div class="flex items-start gap-4">
              <div class="w-14 h-14 bg-[var(--color-success-light)] dark:bg-[var(--color-success)]/10 rounded-2xl flex items-center justify-center flex-shrink-0">
                <el-icon class="w-7 h-7 text-[var(--color-success)]"><DocumentChecked /></el-icon>
              </div>
              <div>
                <h3 class="text-lg font-semibold text-[var(--text-primary)] mb-2">AI自动出题</h3>
                <p class="text-[var(--text-secondary)] text-sm leading-relaxed">
                  根据上传的文档内容，自动生成高质量的选择题和简答题。帮助您检验学习效果，
                  加深对知识点的理解。题目涵盖文档核心内容，是复习备考的理想工具。
                </p>
              </div>
            </div>
          </div>

          <!-- Feature 4 -->
          <div class="el-card p-6">
            <div class="flex items-start gap-4">
              <div class="w-14 h-14 bg-[var(--color-warning-light)] dark:bg-[var(--color-warning)]/10 rounded-2xl flex items-center justify-center flex-shrink-0">
                <el-icon class="w-7 h-7 text-[var(--color-warning)]"><TrendCharts /></el-icon>
              </div>
              <div>
                <h3 class="text-lg font-semibold text-[var(--text-primary)] mb-2">错题分析与学习追踪</h3>
                <p class="text-[var(--text-secondary)] text-sm leading-relaxed">
                  记录每次答题结果，智能分析您的知识薄弱环节。提供详细的学习报告和个性化建议，
                  帮助您针对性地复习，高效提升学习成绩。
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
          <div class="el-card">
            <div class="p-4 border-b border-[var(--border-default)] flex items-center justify-between">
              <h3 class="font-semibold text-[var(--text-primary)]">最近文档</h3>
              <router-link to="/documents" class="text-sm text-[var(--color-primary)] hover:underline">查看全部</router-link>
            </div>
            <div v-if="recentDocs.length === 0" class="p-8 text-center">
              <div class="w-16 h-16 mx-auto mb-4 bg-[var(--bg-tertiary)] rounded-full flex items-center justify-center">
                <el-icon class="w-8 h-8 text-[var(--text-muted)]"><Tickets /></el-icon>
              </div>
              <p class="text-[var(--text-muted)] mb-4">暂无文档</p>
              <router-link to="/upload"><el-button type="primary" size="small">上传文档</el-button></router-link>
            </div>
            <div v-else class="divide-y divide-[var(--border-default)]">
              <div v-for="doc in recentDocs" :key="doc.id" class="p-4 hover:bg-[var(--bg-hover)] cursor-pointer" @click="goToChat(doc.id)">
                <div class="flex items-center gap-3">
                  <div class="w-10 h-10 bg-[var(--color-error-light)] dark:bg-[var(--color-error)]/10 rounded-lg flex items-center justify-center flex-shrink-0">
                    <el-icon class="w-5 h-5 text-[var(--color-error)]"><Tickets /></el-icon>
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
          <div class="el-card">
            <div class="p-4 border-b border-[var(--border-default)] flex items-center justify-between">
              <h3 class="font-semibold text-[var(--text-primary)]">最近对话</h3>
              <router-link to="/chat" class="text-sm text-[var(--color-primary)] hover:underline">查看全部</router-link>
            </div>
            <div v-if="recentChats.length === 0" class="p-8 text-center">
              <div class="w-16 h-16 mx-auto mb-4 bg-[var(--bg-tertiary)] rounded-full flex items-center justify-center">
                <el-icon class="w-8 h-8 text-[var(--text-muted)]"><ChatDotSquare /></el-icon>
              </div>
              <p class="text-[var(--text-muted)] mb-4">暂无对话</p>
              <router-link to="/chat"><el-button type="primary" size="small">开始问答</el-button></router-link>
            </div>
            <div v-else class="divide-y divide-[var(--border-default)]">
              <div v-for="chat in recentChats" :key="chat.session_id" class="p-4 hover:bg-[var(--bg-hover)] cursor-pointer" @click="router.push('/chat')">
                <div class="flex items-center gap-3">
                  <div class="w-10 h-10 bg-[var(--color-accent-light, #f3f0ff)] dark:bg-[var(--color-accent)]/10 rounded-lg flex items-center justify-center flex-shrink-0">
                    <el-icon class="w-5 h-5 text-[var(--color-accent)]"><ChatDotSquare /></el-icon>
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

<script setup>
import { ref, onMounted, onUnmounted, computed, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useDocumentStore } from '../stores/document'
import { useChatStore } from '../stores/chat'
import { Upload, Document, ChatDotSquare, DocumentChecked, Tickets, MagicStick, TrendCharts } from '@element-plus/icons-vue'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'

gsap.registerPlugin(ScrollTrigger)

const router = useRouter()
const documentStore = useDocumentStore()
const chatStore = useChatStore()

// Template refs
const homeContainer = ref(null)
const heroTitle = ref(null)
const heroSubtitle = ref(null)
const heroButtons = ref(null)
const quickActions = ref(null)
const featureCards = ref(null)

let ctx

const recentDocs = computed(() => documentStore.documents.slice(0, 5))
const recentChats = computed(() => chatStore.sessions.slice(0, 5))

function formatDate(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now - date
  if (diff < 86400000) return '今天'
  if (diff < 172800000) return '昨天'
  if (diff < 604800000) return Math.floor(diff / 86400000) + '天前'
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

function goToChat(docId) {
  router.push({ path: '/chat', query: { docId } })
}

onMounted(async () => {
  await Promise.all([documentStore.fetchDocuments(), chatStore.fetchSessions()])

  // Refresh layout after async data fetch (documents/chats may shift DOM)
  await nextTick()
  if (!homeContainer.value) return
  ctx = gsap.context(() => {
    // Task 1: Hero entrance animation
    gsap.from(heroTitle.value, {
      y: 40,
      opacity: 0,
      duration: 0.8,
      ease: 'power2.out'
    })
    gsap.from(heroSubtitle.value, {
      y: 40,
      opacity: 0,
      duration: 0.8,
      delay: 0.2,
      ease: 'power2.out'
    })
    gsap.from(heroButtons.value, {
      y: 40,
      opacity: 0,
      duration: 0.8,
      delay: 0.4,
      ease: 'power2.out'
    })

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