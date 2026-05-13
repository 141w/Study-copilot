<template>
  <div class="min-h-screen">
    <!-- Hero Section -->
    <section class="relative overflow-hidden">
      <div class="absolute inset-0 pastel-gradient opacity-50"></div>
      <div class="relative max-w-6xl mx-auto px-6 py-24">
        <div class="text-center">
          <h1 class="text-5xl font-semibold text-gray-900 mb-6" style="letter-spacing: -0.02em">
            模型配置中心
          </h1>
          <p class="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">
            配置LLM模型参数，优化AI问答体验
          </p>
          <div class="flex gap-4 justify-center">
            <router-link to="/chat" class="btn-primary px-8 py-3 text-base">
              返回问答
            </router-link>
          </div>
        </div>
      </div>
    </section>

    <!-- Config Form -->
    <section class="py-16">
      <div class="max-w-4xl mx-auto px-6">
        <div class="card">
          <div class="p-6">
            <h2 class="text-xl font-semibold text-gray-900 mb-6">模型配置</h2>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                  LLM 模型提供商
                </label>
                <select 
                  v-model="config.provider"
                  @change="onProviderChange"
                  class="w-full px-4 py-3 border border-gray-200 rounded-lg focus:outline-none focus:border-[#010120] focus:ring-1 focus:ring-[#010120] transition-all"
                >
                  <option value="openrouter">OpenRouter</option>
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="google">Google Gemini</option>
                  <option value="custom">自定义兼容</option>
                </select>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                  模型名称
                </label>
                <input 
                  v-model="config.modelName"
                  type="text"
                  :placeholder="modelPlaceholder"
                  class="w-full px-4 py-3 border border-gray-200 rounded-lg focus:outline-none focus:border-[#010120] focus:ring-1 focus:ring-[#010120] transition-all"
                />
              </div>

              <div :class="{ 'md:col-span-2': config.provider === 'custom' }">
                <label class="block text-sm font-medium text-gray-700 mb-2">
                  Base URL
                </label>
                <input 
                  v-model="config.baseUrl"
                  type="text"
                  :placeholder="baseUrlPlaceholder"
                  :disabled="!isCustomProvider"
                  :class="{ 'bg-gray-50': !isCustomProvider }"
                  class="w-full px-4 py-3 border border-gray-200 rounded-lg focus:outline-none focus:border-[#010120] focus:ring-1 focus:ring-[#010120] transition-all"
                />
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                  API Key
                </label>
                <input 
                  v-model="config.apiKey"
                  type="password"
                  :placeholder="apiKeyPlaceholder"
                  class="w-full px-4 py-3 border border-gray-200 rounded-lg focus:outline-none focus:border-[#010120] focus:ring-1 focus:ring-[#010120] transition-all"
                />
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                  温度 (0.0 - 1.0)
                </label>
                <input 
                  v-model.number="config.temperature"
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  class="w-full"
                />
                <div class="flex justify-between text-xs text-gray-500 mt-1">
                  <span>0.0 (确定性)</span>
                  <span>{{ config.temperature }}</span>
                  <span>1.0 (随机性)</span>
                </div>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                  最大响应长度
                </label>
                <input 
                  v-model.number="config.maxTokens"
                  type="number"
                  min="100"
                  max="4096"
                  class="w-full px-4 py-3 border border-gray-200 rounded-lg focus:outline-none focus:border-[#010120] focus:ring-1 focus:ring-[#010120] transition-all"
                  placeholder="2048"
                />
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                  适配器 (适配器模式)
                </label>
                <select 
                  v-model="config.adapter"
                  class="w-full px-4 py-3 border border-gray-200 rounded-lg focus:outline-none focus:border-[#010120] focus:ring-1 focus:ring-[#010120] transition-all"
                >
                  <option value="none">无适配器</option>
                  <option value="lora">LoRA 适配器</option>
                  <option value="ia3">IA³ 适配器</option>
                </select>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                  适配度评分
                </label>
                <div class="flex items-center gap-3">
                  <div class="flex-1">
                    <div class="flex justify-between text-xs text-gray-500 mb-1">
                      <span>OpenRouter 适配度</span>
                      <span>{{ fitScores.openrouter }}%</span>
                    </div>
                    <div class="w-full bg-gray-100 rounded-full h-2">
                      <div 
                        class="bg-[#010120] h-2 rounded-full transition-all duration-300"
                        :style="{ width: fitScores.openrouter + '%' }"
                      ></div>
                    </div>
                  </div>
                  <div class="w-8 text-center text-xs font-medium text-gray-400">
                    ★
                  </div>
                  <div class="flex-1">
                    <div class="flex justify-between text-xs text-gray-500 mb-1">
                      <span>自定义配置适配度</span>
                      <span>{{ fitScores.custom }}%</span>
                    </div>
                    <div class="w-full bg-gray-100 rounded-full h-2">
                      <div 
                        class="bg-[#010120] h-2 rounded-full transition-all duration-300"
                        :style="{ width: fitScores.custom + '%' }"
                      ></div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="mt-6 flex gap-3">
              <button 
                @click="saveConfig"
                class="btn-primary px-6 py-3 font-medium"
              >
                保存配置
              </button>
              <button 
                @click="resetConfig"
                class="btn-secondary px-6 py-3 font-medium"
              >
                重置为默认
              </button>
            </div>
          </div>
        </div>

        <!-- 配置历史 -->
        <div class="mt-8">
          <h3 class="text-lg font-semibold text-gray-900 mb-4">配置历史</h3>
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div 
              v-for="item in configHistory" 
              :key="item.id"
              class="card p-4"
            >
              <div class="flex justify-between items-start mb-2">
                <span class="text-sm font-medium text-gray-900">
                  {{ item.provider }}
                </span>
                <span class="text-xs text-gray-500">
                  {{ formatTime(item.timestamp) }}
                </span>
              </div>
              <p class="text-sm text-gray-600">
                模型: {{ item.modelName }}<br/>
                温度: {{ item.temperature }} | Token: {{ item.maxTokens }}
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore } from '../stores/chat'
import { useConfigStore } from '../stores/config'
import { useDocumentStore } from '../stores/document'

const router = useRouter()
const chatStore = useChatStore()
const configStore = useConfigStore()
const documentStore = useDocumentStore()

const config = ref({
  apiKey: localStorage.getItem('llmApiKey') || '',
  baseUrl: localStorage.getItem('llmBaseUrl') || 'https://api.openai.com/v1',
  provider: 'openrouter',
  modelName: 'gpt-4o-mini',
  temperature: 0.7,
  maxTokens: 2048,
  adapter: 'none'
})

const configHistory = ref([])

const providerDefaults = {
  openrouter: { baseUrl: 'https://openrouter.ai/api/v1', model: 'openai/gpt-4o-mini', apiKey: 'sk-or-...' },
  openai: { baseUrl: 'https://api.openai.com/v1', model: 'gpt-4o-mini', apiKey: 'sk-...' },
  anthropic: { baseUrl: 'https://api.anthropic.com', model: 'claude-3-haiku-20240307', apiKey: 'sk-ant-...' },
  google: { baseUrl: 'https://generativelanguage.googleapis.com/v1', model: 'gemini-1.5-flash-latest', apiKey: 'AIza...' },
  custom: { baseUrl: 'https://api.openai.com/v1', model: 'gpt-4o-mini', apiKey: 'sk-...' }
}

const isCustomProvider = computed(() => config.value.provider === 'custom')
const baseUrlPlaceholder = computed(() => providerDefaults[config.value.provider]?.baseUrl || '')
const apiKeyPlaceholder = computed(() => providerDefaults[config.value.provider]?.apiKey || '')
const modelPlaceholder = computed(() => providerDefaults[config.value.provider]?.model || '')

function onProviderChange() {
  const defaults = providerDefaults[config.value.provider]
  config.value.baseUrl = defaults.baseUrl
  config.value.modelName = defaults.model
}

const fitScores = computed(() => {
  let score = 80
  if (config.value.provider === 'openrouter') score += 10
  if (config.value.adapter !== 'none') score += 5
  if (config.value.temperature >= 0.5 && config.value.temperature <= 0.8) score += 10
  return {
    openrouter: score,
    custom: Math.min(100, score + Math.floor(Math.random() * 10))
  }
})

async function saveConfig() {
  try {
    await configStore.saveLLMConfig({
      provider: config.value.provider,
      api_key: config.value.apiKey,
      base_url: config.value.baseUrl,
      model_name: config.value.modelName,
      temperature: Math.round(config.value.temperature * 10),
      max_tokens: config.value.maxTokens
    })
    alert('配置保存成功！')
  } catch (error) {
    alert('保存失败：' + (error.message || '未知错误'))
  }
}

function resetConfig() {
  const defaults = providerDefaults[config.value.provider] || providerDefaults.openrouter
  config.value = {
    apiKey: '',
    baseUrl: defaults.baseUrl,
    provider: config.value.provider,
    modelName: defaults.model,
    temperature: 0.7,
    maxTokens: 2048,
    adapter: 'none'
  }
  chatStore.config.apiKey = ''
  chatStore.config.baseUrl = defaults.baseUrl
  chatStore.config.provider = config.value.provider
  chatStore.config.modelName = defaults.model
  chatStore.config.temperature = 0.7
  chatStore.config.maxTokens = 2048
  chatStore.config.adapter = 'none'
}

function formatTime(timestamp) {
  return new Date(timestamp).toLocaleString('zh-CN')
}

onMounted(async () => {
  const dbConfig = await configStore.fetchLLMConfigWithSecret()
  if (dbConfig && dbConfig.id) {
    config.value = {
      apiKey: dbConfig.api_key || '',
      baseUrl: dbConfig.base_url || '',
      provider: dbConfig.provider,
      modelName: dbConfig.model_name,
      temperature: dbConfig.temperature / 10,
      maxTokens: dbConfig.max_tokens,
      adapter: 'none'
    }
  } else {
    const defaults = providerDefaults.openrouter
    config.value = {
      apiKey: '',
      baseUrl: defaults.baseUrl,
      provider: 'openrouter',
      modelName: defaults.model,
      temperature: 0.7,
      maxTokens: 2048,
      adapter: 'none'
    }
  }
})
</script>

<style scoped>
.gradient-text {
  background: linear-gradient(135deg, #010120 0%, #3b82f6 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.card {
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
}
</style>