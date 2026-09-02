<template>
  <div class="max-w-4xl mx-auto px-6 py-8">
    <!-- Header（与其他设置页统一：标题 + 副标题，替换原 hero 大横幅） -->
    <div class="flex items-center justify-between mb-8">
      <div>
        <h1 class="text-2xl font-semibold text-[var(--text-primary)]">模型配置</h1>
        <p class="text-sm text-[var(--text-muted)] mt-1">配置 LLM 模型参数，优化 AI 问答体验</p>
      </div>
      <router-link to="/chat">
        <el-button>返回问答</el-button>
      </router-link>
    </div>

    <div class="card p-6">
      <el-form ref="formRef" :model="config" :rules="formRules" label-position="top">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <el-form-item label="LLM 模型提供商" prop="provider">
            <el-select v-model="config.provider" @change="onProviderChange">
              <el-option value="openrouter" label="OpenRouter" />
              <el-option value="openai" label="OpenAI" />
              <el-option value="anthropic" label="Anthropic" />
              <el-option value="google" label="Google Gemini" />
              <el-option value="custom" label="自定义兼容" />
            </el-select>
          </el-form-item>

          <el-form-item label="模型名称" prop="modelName">
            <el-input v-model="config.modelName" :placeholder="modelPlaceholder" />
          </el-form-item>

          <el-form-item label="Base URL" prop="baseUrl">
            <el-input
              v-model="config.baseUrl"
              :placeholder="baseUrlPlaceholder"
              :disabled="!isCustomProvider"
            />
          </el-form-item>

          <el-form-item label="API Key">
            <el-input
              v-model="config.apiKey"
              type="password"
              show-password
              :placeholder="apiKeyPlaceholder"
            />
            <p v-if="savedKeyMasked" class="mt-1.5 text-xs text-[var(--text-muted)]">
              已保存：{{ savedKeyMasked }}（留空保存 = 保留原 Key，输入新值 = 覆盖）
            </p>
          </el-form-item>

          <el-form-item label="温度 (0.0 - 1.0)">
            <div class="w-full">
              <el-slider
                v-model="config.temperature"
                :min="0"
                :max="1"
                :step="0.1"
                show-stops
              />
              <div class="flex justify-between text-xs text-[var(--text-muted)] mt-1">
                <span>0.0 (确定性)</span>
                <span>{{ config.temperature }}</span>
                <span>1.0 (随机性)</span>
              </div>
            </div>
          </el-form-item>

          <el-form-item label="最大响应长度" prop="maxTokens">
            <el-input-number
              v-model="config.maxTokens"
              :min="100"
              :max="4096"
              :step="256"
              class="w-full"
            />
          </el-form-item>

          <el-form-item label="Embedding 模型">
            <el-select v-model="config.embeddingModel" @change="onEmbeddingModelChange">
              <el-option value="shibing624/text2vec-base-chinese" label="text2vec-base-chinese (中文, 768维)" />
              <el-option value="BAAI/bge-m3" label="bge-m3 (多语言, 1024维)" />
            </el-select>
          </el-form-item>

          <el-form-item label="Embedding 维度">
            <el-input :value="config.embeddingDimension" disabled />
          </el-form-item>
        </div>

        <div class="mt-6 flex gap-3">
          <el-button type="primary" :loading="saving" @click="saveConfig">保存配置</el-button>
          <el-button @click="resetConfig">重置为默认</el-button>
        </div>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { useConfigStore } from '../stores/config'
import { useToastStore } from '../stores/toast'

type ProviderKey = 'openrouter' | 'openai' | 'anthropic' | 'google' | 'custom'

interface ModelConfigForm {
  apiKey: string
  baseUrl: string
  provider: ProviderKey
  modelName: string
  temperature: number
  maxTokens: number
  embeddingModel: string
  embeddingDimension: number
}

const configStore = useConfigStore()
const toast = useToastStore()

const formRef = ref<FormInstance | null>(null)
const saving = ref(false)

const config = ref<ModelConfigForm>({
  apiKey: '',
  baseUrl: 'https://api.openai.com/v1',
  provider: 'openrouter',
  modelName: 'gpt-4o-mini',
  temperature: 0.7,
  maxTokens: 2048,
  embeddingModel: 'shibing624/text2vec-base-chinese',
  embeddingDimension: 768
})

// P0-6：表单校验（原版仅 HTML 属性，可手动越界）
const formRules: FormRules = {
  provider: [{ required: true, message: '请选择提供商', trigger: 'change' }],
  modelName: [{ required: true, message: '请输入模型名称', trigger: 'blur' }],
  baseUrl: [{ required: true, message: '请输入 Base URL', trigger: 'blur' }],
  maxTokens: [
    { type: 'number', min: 100, max: 4096, message: '范围 100 - 4096', trigger: 'change' }
  ]
}

// 已保存 Key 的掩码展示值（如 sk-***xyz）；输入框留空保存 = 保留原 Key
const savedKeyMasked = ref('')

const providerDefaults: Record<ProviderKey, { baseUrl: string; model: string; apiKey: string }> = {
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

function onProviderChange(): void {
  const defaults = providerDefaults[config.value.provider]
  config.value.baseUrl = defaults.baseUrl
  config.value.modelName = defaults.model
}

const embeddingDimensionMap: Record<string, number> = {
  'shibing624/text2vec-base-chinese': 768,
  'BAAI/bge-m3': 1024
}

function onEmbeddingModelChange(): void {
  config.value.embeddingDimension = embeddingDimensionMap[config.value.embeddingModel] || 768
}

async function saveConfig(): Promise<void> {
  // P0-6：alert() → toast；先校验表单
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  saving.value = true
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
    savedKeyMasked.value = (await configStore.fetchLLMConfig())?.api_key_masked || ''
    config.value.apiKey = ''
    toast.success('配置保存成功')
  } catch (error) {
    toast.error('保存失败：' + ((error as Error).message || '未知错误'))
  } finally {
    saving.value = false
  }
}

function resetConfig(): void {
  const defaults = providerDefaults[config.value.provider] || providerDefaults.openrouter
  config.value = {
    apiKey: '',
    baseUrl: defaults.baseUrl,
    provider: config.value.provider,
    modelName: defaults.model,
    temperature: 0.7,
    maxTokens: 2048,
    embeddingModel: 'shibing624/text2vec-base-chinese',
    embeddingDimension: 768
  }
  formRef.value?.clearValidate()
  toast.info('已重置为默认值（未保存）')
}

onMounted(async () => {
  // 安全设计（2026-08-19 起沿用）：/config/llm 不返回明文 Key；
  // 已保存的 Key 只显示掩码；留空保存 = 保留原 Key（后端已支持）。
  const dbConfig = await configStore.fetchLLMConfig()
  if (dbConfig && dbConfig.id) {
    savedKeyMasked.value = dbConfig.api_key_masked || ''
    config.value = {
      apiKey: '',
      baseUrl: dbConfig.base_url || '',
      provider: dbConfig.provider as ProviderKey,
      modelName: dbConfig.model_name,
      temperature: dbConfig.temperature ?? 0.7,
      maxTokens: dbConfig.max_tokens ?? 2048,
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
      embeddingModel: 'shibing624/text2vec-base-chinese',
      embeddingDimension: 768
    }
  }
})
</script>
