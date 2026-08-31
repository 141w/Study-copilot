<template>
  <div class="min-h-screen">
    <!-- Hero Section -->
    <section class="relative overflow-hidden">
      <div class="absolute inset-0 pastel-gradient opacity-50"></div>
      <div class="relative max-w-6xl mx-auto px-6 py-24">
        <div class="text-center">
          <h1 class="text-5xl font-semibold text-[var(--text-primary)] mb-6" style="letter-spacing: -0.02em">
            模型配置中心
          </h1>
          <p class="text-xl text-[var(--text-secondary)] mb-8 max-w-2xl mx-auto">
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
            <h2 class="text-xl font-semibold text-[var(--text-primary)] mb-6">模型配置</h2>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label class="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                  LLM 模型提供商
                </label>
                <select 
                  v-model="config.provider"
                  @change="onProviderChange"
                  class="w-full px-4 py-3 border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--border-focus)] focus:ring-1 focus:ring-[var(--color-primary)] transition-all"
                >
                  <option value="openrouter">OpenRouter</option>
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="google">Google Gemini</option>
                  <option value="custom">自定义兼容</option>
                </select>
              </div>

              <div>
                <label class="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                  模型名称
                </label>
                <input 
                  v-model="config.modelName"
                  type="text"
                  :placeholder="modelPlaceholder"
                  class="w-full px-4 py-3 border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--border-focus)] focus:ring-1 focus:ring-[var(--color-primary)] transition-all"
                />
              </div>

              <div :class="{ 'md:col-span-2': config.provider === 'custom' }">
                <label class="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                  Base URL
                </label>
                <input 
                  v-model="config.baseUrl"
                  type="text"
                  :placeholder="baseUrlPlaceholder"
                  :disabled="!isCustomProvider"
                  :class="{ 'bg-[var(--bg-secondary)]': !isCustomProvider }"
                  class="w-full px-4 py-3 border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--border-focus)] focus:ring-1 focus:ring-[var(--color-primary)] transition-all"
                />
              </div>

              <div>
                <label class="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                  API Key
                </label>
                <input 
                  v-model="config.apiKey"
                  type="password"
                  :placeholder="apiKeyPlaceholder"
                  class="w-full px-4 py-3 border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--border-focus)] focus:ring-1 focus:ring-[var(--color-primary)] transition-all"
                />
                <p v-if="savedKeyMasked" class="mt-1.5 text-xs text-[var(--text-muted)]">
                  已保存：{{ savedKeyMasked }}（留空保存 = 保留原 Key，输入新值 = 覆盖）
                </p>
              </div>

              <div>
                <label class="block text-sm font-medium text-[var(--text-secondary)] mb-2">
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
                <div class="flex justify-between text-xs text-[var(--text-muted)] mt-1">
                  <span>0.0 (确定性)</span>
                  <span>{{ config.temperature }}</span>
                  <span>1.0 (随机性)</span>
                </div>
              </div>

              <div>
                <label class="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                  最大响应长度
                </label>
                <input 
                  v-model.number="config.maxTokens"
                  type="number"
                  min="100"
                  max="4096"
                  class="w-full px-4 py-3 border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--border-focus)] focus:ring-1 focus:ring-[var(--color-primary)] transition-all"
                  placeholder="2048"
                />
              </div>

              <div>
                <label class="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                  适配器 (适配器模式)
                </label>
                <select
                  v-model="config.adapter"
                  class="w-full px-4 py-3 border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--border-focus)] focus:ring-1 focus:ring-[var(--color-primary)] transition-all"
                >
                  <option value="none">无适配器</option>
                  <option value="lora">LoRA 适配器</option>
                  <option value="ia3">IA³ 适配器</option>
                </select>
              </div>

              <div>
                <label class="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                  Embedding 模型
                </label>
                <select
                  v-model="config.embeddingModel"
                  @change="onEmbeddingModelChange"
                  class="w-full px-4 py-3 border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--border-focus)] focus:ring-1 focus:ring-[var(--color-primary)] transition-all"
                >
                  <option value="shibing624/text2vec-base-chinese">text2vec-base-chinese (中文, 768维)</option>
                  <option value="BAAI/bge-m3">bge-m3 (多语言, 1024维)</option>
                </select>
              </div>

              <div>
                <label class="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                  Embedding 维度
                </label>
                <input
                  :value="config.embeddingDimension"
                  type="text"
                  disabled
                  class="w-full px-4 py-3 border border-[var(--border-default)] rounded-lg bg-[var(--bg-secondary)] text-[var(--text-muted)] cursor-not-allowed"
                />
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
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useChatStore } from '../stores/chat'
import { useConfigStore } from '../stores/config'

const chatStore = useChatStore()
const configStore = useConfigStore()

const config = ref({
  apiKey: localStorage.getItem('llmApiKey') || '',
  baseUrl: localStorage.getItem('llmBaseUrl') || 'https://api.openai.com/v1',
  provider: 'openrouter',
  modelName: 'gpt-4o-mini',
  temperature: 0.7,
  maxTokens: 2048,
  adapter: 'none',
  embeddingModel: 'shibing624/text2vec-base-chinese',
  embeddingDimension: 768
})

// 已保存 Key 的掩码展示值（如 sk-***xyz）；输入框留空保存 = 保留原 Key
const savedKeyMasked = ref('')

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

const embeddingDimensionMap = {
  'shibing624/text2vec-base-chinese': 768,
  'BAAI/bge-m3': 1024
}

function onEmbeddingModelChange() {
  config.value.embeddingDimension = embeddingDimensionMap[config.value.embeddingModel] || 768
}

async function saveConfig() {
  try {
    await configStore.saveLLMConfig({
      provider: config.value.provider,
      api_key: config.value.apiKey,
      base_url: config.value.baseUrl,
      model_name: config.value.modelName,
      temperature: config.value.temperature,
      max_tokens: config.value.maxTokens,
      embedding_model: config.value.embeddingModel,
      embedding_dimension: config.value.embeddingDimension
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
    adapter: 'none',
    embeddingModel: 'shibing624/text2vec-base-chinese',
    embeddingDimension: 768
  }
  chatStore.config.apiKey = ''
  chatStore.config.baseUrl = defaults.baseUrl
  chatStore.config.provider = config.value.provider
  chatStore.config.modelName = defaults.model
  chatStore.config.temperature = 0.7
  chatStore.config.maxTokens = 2048
  chatStore.config.adapter = 'none'
}

onMounted(async () => {
  // 安全修复（2026-08-19）：改用不含明文的 /config/llm。
  // 已保存的 Key 只显示掩码；留空保存 = 保留原 Key（后端已支持）。
  const dbConfig = await configStore.fetchLLMConfig()
  if (dbConfig && dbConfig.id) {
    savedKeyMasked.value = dbConfig.api_key_masked || ''
    config.value = {
      apiKey: '',
      baseUrl: dbConfig.base_url || '',
      provider: dbConfig.provider,
      modelName: dbConfig.model_name,
      temperature: dbConfig.temperature,
      maxTokens: dbConfig.max_tokens,
      adapter: 'none',
      embeddingModel: dbConfig.embedding_model || 'shibing624/text2vec-base-chinese',
      embeddingDimension: dbConfig.embedding_dimension || 768
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
      adapter: 'none',
      embeddingModel: 'shibing624/text2vec-base-chinese',
      embeddingDimension: 768
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

</style>