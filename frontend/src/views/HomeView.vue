<template>
  <div class="min-h-screen">
    <!-- Hero Section -->
    <section class="relative overflow-hidden">
      <div class="absolute inset-0 pastel-gradient opacity-50"></div>
      <div class="relative max-w-6xl mx-auto px-6 py-20">
        <div class="text-center">
          <h1 class="text-5xl font-semibold text-gray-900 mb-6" style="letter-spacing: -0.02em">
            欢迎使用<span class="gradient-text">Study Copilot</span>
          </h1>
          <p class="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">
            您的AI学习助手<br/>
            文档解析 · 智能问答 · AI出题 · 错题分析
          </p>
          <div class="flex gap-4 justify-center">
            <router-link to="/upload" class="btn-primary px-8 py-3 text-base">上传文档</router-link>
            <router-link to="/chat" class="btn-secondary px-8 py-3 text-base">开始问答</router-link>
          </div>
        </div>
      </div>
    </section>

    <!-- Quick Actions -->
    <section class="py-10">
      <div class="max-w-6xl mx-auto px-6">
        <h2 class="text-xl font-semibold text-gray-900 mb-6">快速开始</h2>
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
          <router-link to="/upload" class="card p-6 hover:border-[#010120] border-2 transition-colors group">
            <div class="w-12 h-12 bg-red-50 rounded-xl flex items-center justify-center mb-4 group-hover:bg-red-100 transition-colors">
              <svg class="w-6 h-6 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
            </div>
            <h3 class="font-semibold text-gray-900 mb-1">上传文档</h3>
            <p class="text-sm text-gray-500">上传PDF学习资料</p>
          </router-link>
          
          <router-link to="/documents" class="card p-6 hover:border-[#010120] border-2 transition-colors group">
            <div class="w-12 h-12 bg-blue-50 rounded-xl flex items-center justify-center mb-4 group-hover:bg-blue-100 transition-colors">
              <svg class="w-6 h-6 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
              </svg>
            </div>
            <h3 class="font-semibold text-gray-900 mb-1">文档管理</h3>
            <p class="text-sm text-gray-500">查看已上传文档</p>
          </router-link>
          
          <router-link to="/chat" class="card p-6 hover:border-[#010120] border-2 transition-colors group">
            <div class="w-12 h-12 bg-purple-50 rounded-xl flex items-center justify-center mb-4 group-hover:bg-purple-100 transition-colors">
              <svg class="w-6 h-6 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </div>
            <h3 class="font-semibold text-gray-900 mb-1">智能问答</h3>
            <p class="text-sm text-gray-500">基于文档的RAG问答</p>
          </router-link>
          
          <router-link to="/quiz" class="card p-6 hover:border-[#010120] border-2 transition-colors group">
            <div class="w-12 h-12 bg-green-50 rounded-xl flex items-center justify-center mb-4 group-hover:bg-green-100 transition-colors">
              <svg class="w-6 h-6 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
              </svg>
            </div>
            <h3 class="font-semibold text-gray-900 mb-1">AI出题</h3>
            <p class="text-sm text-gray-500">生成练习题</p>
          </router-link>
        </div>
      </div>
    </section>

    <!-- Features Introduction -->
    <section class="py-10 bg-gray-50">
      <div class="max-w-6xl mx-auto px-6">
        <h2 class="text-xl font-semibold text-gray-900 mb-6">功能介绍</h2>
        
        <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
          <!-- Feature 1 -->
          <div class="card p-6">
            <div class="flex items-start gap-4">
              <div class="w-14 h-14 bg-red-50 rounded-xl flex items-center justify-center flex-shrink-0">
                <svg class="w-7 h-7 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <div>
                <h3 class="text-lg font-semibold text-gray-900 mb-2">智能文档解析</h3>
                <p class="text-gray-600 text-sm leading-relaxed">
                  支持PDF文件上传，采用先进的AI技术解析文档内容。能够自动识别并提取文本、表格、结构化信息，
                  构建高效的向量知识库，让您的文档变成可检索的知识体系。
                </p>
              </div>
            </div>
          </div>

          <!-- Feature 2 -->
          <div class="card p-6">
            <div class="flex items-start gap-4">
              <div class="w-14 h-14 bg-purple-50 rounded-xl flex items-center justify-center flex-shrink-0">
                <svg class="w-7 h-7 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.548A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.548z" />
                </svg>
              </div>
              <div>
                <h3 class="text-lg font-semibold text-gray-900 mb-2">RAG智能问答</h3>
                <p class="text-gray-600 text-sm leading-relaxed">
                  基于RAG（检索增强生成）技术，从您的文档向量库中检索相关信息，结合大语言模型生成准确答案。
                  不仅提供答案，还会标注参考来源，方便您追溯原文、深入学习。
                </p>
              </div>
            </div>
          </div>

          <!-- Feature 3 -->
          <div class="card p-6">
            <div class="flex items-start gap-4">
              <div class="w-14 h-14 bg-green-50 rounded-xl flex items-center justify-center flex-shrink-0">
                <svg class="w-7 h-7 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                </svg>
              </div>
              <div>
                <h3 class="text-lg font-semibold text-gray-900 mb-2">AI自动出题</h3>
                <p class="text-gray-600 text-sm leading-relaxed">
                  根据上传的文档内容，自动生成高质量的选择题和简答题。帮助您检验学习效果，
                  加深对知识点的理解。题目涵盖文档核心内容，是复习备考的理想工具。
                </p>
              </div>
            </div>
          </div>

          <!-- Feature 4 -->
          <div class="card p-6">
            <div class="flex items-start gap-4">
              <div class="w-14 h-14 bg-orange-50 rounded-xl flex items-center justify-center flex-shrink-0">
                <svg class="w-7 h-7 text-orange-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <div>
                <h3 class="text-lg font-semibold text-gray-900 mb-2">错题分析与学习追踪</h3>
                <p class="text-gray-600 text-sm leading-relaxed">
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
          <div class="card">
            <div class="p-4 border-b border-gray-100 flex items-center justify-between">
              <h3 class="font-semibold text-gray-900">最近文档</h3>
              <router-link to="/documents" class="text-sm text-[#010120] hover:underline">查看全部</router-link>
            </div>
            <div v-if="recentDocs.length === 0" class="p-8 text-center">
              <div class="w-16 h-16 mx-auto mb-4 bg-gray-100 rounded-full flex items-center justify-center">
                <svg class="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <p class="text-gray-500 mb-4">暂无文档</p>
              <router-link to="/upload" class="btn-secondary text-sm">上传文档</router-link>
            </div>
            <div v-else class="divide-y divide-gray-50">
              <div v-for="doc in recentDocs" :key="doc.id" class="p-4 hover:bg-gray-50 cursor-pointer" @click="goToChat(doc.id)">
                <div class="flex items-center gap-3">
                  <div class="w-10 h-10 bg-red-50 rounded-lg flex items-center justify-center flex-shrink-0">
                    <svg class="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <div class="flex-1 min-w-0">
                    <div class="text-sm font-medium text-gray-900 truncate">{{ doc.filename }}</div>
                    <div class="text-xs text-gray-500">{{ doc.chunk_count || 0 }} chunks · {{ formatDate(doc.created_at) }}</div>
                  </div>
                  <span v-if="doc.status === 'ready'" class="text-xs px-2 py-1 bg-green-50 text-green-600 rounded-full">就绪</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Recent Chats -->
          <div class="card">
            <div class="p-4 border-b border-gray-100 flex items-center justify-between">
              <h3 class="font-semibold text-gray-900">最近对话</h3>
              <router-link to="/chat" class="text-sm text-[#010120] hover:underline">查看全部</router-link>
            </div>
            <div v-if="recentChats.length === 0" class="p-8 text-center">
              <div class="w-16 h-16 mx-auto mb-4 bg-gray-100 rounded-full flex items-center justify-center">
                <svg class="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <p class="text-gray-500 mb-4">暂无对话</p>
              <router-link to="/chat" class="btn-secondary text-sm">开始问答</router-link>
            </div>
            <div v-else class="divide-y divide-gray-50">
              <div v-for="chat in recentChats" :key="chat.session_id" class="p-4 hover:bg-gray-50 cursor-pointer" @click="router.push('/chat')">
                <div class="flex items-center gap-3">
                  <div class="w-10 h-10 bg-purple-50 rounded-lg flex items-center justify-center flex-shrink-0">
                    <svg class="w-5 h-5 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                    </svg>
                  </div>
                  <div class="flex-1 min-w-0">
                    <div class="text-sm font-medium text-gray-900 truncate">{{ chat.title || '新对话' }}</div>
                    <div class="text-xs text-gray-500">{{ formatDate(chat.created_at) }}</div>
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
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useDocumentStore } from '../stores/document'
import { useChatStore } from '../stores/chat'

const router = useRouter()
const documentStore = useDocumentStore()
const chatStore = useChatStore()

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

onMounted(() => {
  documentStore.fetchDocuments()
  chatStore.fetchSessions()
})
</script>