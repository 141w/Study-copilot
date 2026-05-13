<template>
  <div 
    class="flex gap-4 mb-4"
    :class="message.role === 'user' ? 'flex-row-reverse' : ''"
  >
    <div 
      class="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
      :class="message.role === 'user' ? 'bg-[#010120]' : 'bg-gray-100'"
    >
      <svg v-if="message.role === 'user'" class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
      </svg>
      <svg v-else class="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.572 3.572 0 0014 18v0a3.572 3.572 0 00-1.414 2.606l.548.547a5 5 0 010 7.072l-.548.547A3.572 3.572 0 0014 22a3.572 3.572 0 00-1.414-2.606l.548-.547a5 5 0 010-7.072z" />
      </svg>
    </div>
    
    <div 
      class="max-w-[70%] px-4 py-3 rounded-xl"
      :class="message.role === 'user' 
        ? 'bg-[#010120] text-white rounded-br-sm' 
        : 'bg-gray-50 text-gray-900 border border-gray-100 rounded-bl-sm'"
    >
      <!-- Copy button -->
      <div v-if="message.role === 'assistant'" class="flex justify-end mb-1">
        <button 
          @click="copyContent"
          class="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1"
          title="复制内容"
        >
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
          {{ copied ? '已复制' : '复制' }}
        </button>
      </div>
      
      <!-- Content with expand/collapse -->
      <div :class="{ 'line-clamp-6': isLongContent && !expanded }">
        <div v-html="renderedContent" class="prose prose-sm max-w-none" :class="{ 'code-block-custom': hasCode }"></div>
      </div>
      
      <!-- Expand/Collapse button -->
      <button 
        v-if="isLongContent"
        @click="expanded = !expanded"
        class="text-xs text-gray-400 hover:text-gray-600 mt-1"
      >
        {{ expanded ? '收起' : '展开全部' }}
      </button>
      
      <!-- Sources -->
      <div v-if="message.sources && message.sources.length" class="mt-3 pt-3 border-t border-gray-100">
        <p class="text-xs text-gray-400 mb-2">参考来源:</p>
        <div 
          v-for="(source, idx) in message.sources" 
          :key="idx"
          class="text-xs bg-gray-100 rounded mb-2 overflow-hidden"
        >
          <div 
            class="px-2 py-1 bg-gray-200 cursor-pointer flex justify-between items-center"
            @click="toggleSource(idx)"
          >
            <span class="font-medium text-gray-600">
              {{ getDocName(source.document_id) }}
              <span class="text-gray-400 ml-1">({{ (source.relevance_score * 100).toFixed(0) }}% 匹配)</span>
            </span>
            <svg 
              class="w-4 h-4 text-gray-500 transition-transform" 
              :class="{ 'rotate-180': expandedSources[idx] }"
              fill="none" stroke="currentColor" viewBox="0 0 24 24"
            >
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
            </svg>
          </div>
          <div 
            v-show="expandedSources[idx]"
            class="px-2 py-2 text-gray-600 whitespace-pre-wrap"
          >
            {{ source.text }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import MarkdownIt from 'markdown-it'
import { useDocumentStore } from '../../stores/document'
import { useToastStore } from '../../stores/toast'

const props = defineProps({
  message: {
    type: Object,
    required: true
  }
})

const documentStore = useDocumentStore()
const toastStore = useToastStore()
const expandedSources = reactive({})
const expanded = ref(false)
const copied = ref(false)

const md = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true
})

const renderedContent = computed(() => {
  return md.render(props.message.content)
})

const isLongContent = computed(() => {
  return props.message.content.length > 500
})

const hasCode = computed(() => {
  return props.message.content.includes('```') || props.message.content.includes('`')
})

function toggleSource(idx) {
  expandedSources[idx] = !expandedSources[idx]
}

function getDocName(docId) {
  const doc = documentStore.documents.find(d => d.id === docId)
  return doc ? doc.filename : `文档 ${docId?.substring(0, 8)}`
}

async function copyContent() {
  try {
    await navigator.clipboard.writeText(props.message.content)
    copied.value = true
    toastStore.show('复制成功', 'success')
    setTimeout(() => { copied.value = false }, 2000)
  } catch (err) {
    toastStore.show('复制失败', 'error')
  }
}
</script>

<style scoped>
.code-block-custom :deep(pre) {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
  font-size: 13px;
  line-height: 1.5;
}

.code-block-custom :deep(code) {
  font-family: 'Consolas', 'Monaco', monospace;
}

.code-block-custom :deep(p code) {
  background: #f3f4f6;
  color: #c7254e;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 0.9em;
}

.line-clamp-6 {
  display: -webkit-box;
  -webkit-line-clamp: 6;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>