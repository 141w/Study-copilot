<template>
  <div class="max-w-4xl mx-auto px-6 py-8">
    <!-- Header（与其他设置页统一：标题 + 副标题，替换原 hero 大横幅） -->
    <div class="flex items-center justify-between mb-8">
      <div>
        <h1 class="text-2xl font-semibold text-[var(--text-primary)]">消息格式</h1>
        <p class="text-sm text-[var(--text-muted)] mt-1">选择 LLM 消息格式，适配不同的 API 提供商</p>
      </div>
      <router-link to="/chat">
        <el-button>返回问答</el-button>
      </router-link>
    </div>

    <div class="card p-6">
      <el-form ref="formRef" :model="config" :rules="formRules" label-position="top">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <el-form-item label="消息格式" prop="messageFormat">
            <el-select v-model="config.messageFormat" @change="onFormatChange">
              <el-option value="openai" label="OpenAI 格式" />
              <el-option value="anthropic" label="Anthropic 格式" />
              <el-option value="gemini" label="Gemini 格式" />
              <el-option value="ollama" label="Ollama 格式" />
            </el-select>
          </el-form-item>

          <el-form-item label="模型名称" prop="modelName">
            <el-input v-model="config.modelName" placeholder="例如：gpt-4o-mini" />
          </el-form-item>

          <el-form-item label="Base URL" prop="baseUrl">
            <el-input v-model="config.baseUrl" placeholder="https://api.openai.com/v1" />
          </el-form-item>

          <el-form-item label="API Key">
            <el-input
              v-model="config.apiKey"
              type="password"
              show-password
              :placeholder="apiKeyPlaceholder"
            />
            <p v-if="savedKeyMasked" class="mt-1.5 text-xs text-[var(--text-muted)]">
              已保存：{{ savedKeyMasked }}（留空保存则保留原 Key；输入新值则覆盖）
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
                <span>0.0 偏确定</span>
                <span>{{ config.temperature }}</span>
                <span>1.0 偏随机</span>
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
import { ref, onMounted } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { useConfigStore } from '../stores/config'
import { useToastStore } from '../stores/toast'

type MessageFormat = 'openai' | 'anthropic' | 'gemini' | 'ollama'

interface ModelConfigForm {
  apiKey: string
  baseUrl: string
  messageFormat: MessageFormat
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
  messageFormat: 'openai',
  modelName: 'gpt-4o-mini',
  temperature: 0.7,
  maxTokens: 2048,
  embeddingModel: 'shibing624/text2vec-base-chinese',
  embeddingDimension: 768
})

// P0-6：表单校验
const formRules: FormRules = {
  messageFormat: [{ required: true, message: '请选择消息格式', trigger: 'change' }],
  modelName: [{ required: true, message: '请输入模型名称', trigger: 'blur' }],
  baseUrl: [{ required: true, message: '请输入 Base URL', trigger: 'blur' }],
  maxTokens: [
    { type: 'number', min: 100, max: 4096, message: '范围 100 - 4096', trigger: 'change' }
  ]
}

// 已保存 Key 的掩码展示值
const savedKeyMasked = ref('')

const apiKeyPlaceholder = ref('sk-...')
const savedKeyOverwritten = ref(false)

// 消息格式 → 推荐 Base URL / 模型 / API Key 占位
const formatDefaults: Record<MessageFormat, { baseUrl: string; model: string; apiKey: string }> = {
  openai:    { baseUrl: 'https://api.openai.com/v1',            model: 'gpt-4o-mini',         apiKey: 'sk-...' },
  anthropic: { baseUrl: 'https://api.anthropic.com',              model: 'claude-3-haiku-20240307', apiKey: 'sk-ant-...' },
  gemini:    { baseUrl: 'https://generativelanguage.googleapis.com/v1', model: 'gemini-1.5-flash-latest', apiKey: 'AIza...' },
  ollama:    { baseUrl: 'http://localhost:11434/v1',              model: 'llama3.1',            apiKey: 'ollama' },
}

function onFormatChange(): void {
  const defaults = formatDefaults[config.value.messageFormat]
  if (defaults && !savedKeyOverwritten.value) {
    config.value.baseUrl = defaults.baseUrl
    config.value.modelName = defaults.model
  }
  apiKeyPlaceholder.value = defaults?.apiKey || 'sk-...'
}

const embeddingDimensionMap: Record<string, number> = {
  'shibing624/text2vec-base-chinese': 768,
  'BAAI/bge-m3': 1024
}

function onEmbeddingModelChange(): void {
  config.value.embeddingDimension = embeddingDimensionMap[config.value.embeddingModel] || 768
}

async function saveConfig(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    await configStore.saveLLMConfig({
      provider: config.value.messageFormat,
      api_key: config.value.apiKey,
      base_url: config.value.baseUrl,
      model_name: config.value.modelName,
      temperature: config.value.temperature,
      max_tokens: config.value.maxTokens,
      embedding_model: config.value.embeddingModel,
      embedding_dimension: config.value.embeddingDimension,
      message_format: config.value.messageFormat,
    })
    savedKeyMasked.value = (await configStore.fetchLLMConfig())?.api_key_masked || ''
    config.value.apiKey = ''
    savedKeyOverwritten.value = false
    toast.success('配置保存成功')
  } catch (error) {
    toast.error('保存失败：' + ((error as Error).message || '未知错误'))
  } finally {
    saving.value = false
  }
}

function resetConfig(): void {
  const defaults = formatDefaults[config.value.messageFormat]
  config.value = {
    apiKey: '',
    baseUrl: defaults.baseUrl,
    messageFormat: config.value.messageFormat,
    modelName: defaults.model,
    temperature: 0.7,
    maxTokens: defaults.model === 'llama3.1' ? 4096 : 2048,
    embeddingModel: 'shibing624/text2vec-base-chinese',
    embeddingDimension: 768
  }
  savedKeyOverwritten.value = false
  formRef.value?.clearValidate()
  toast.info('已重置为默认值（未保存）')
}

onMounted(async () => {
  // 安全设计（2026-08-19 起沿用）：/config/llm 不返回明文 Key；
  // 已保存的 Key 只显示掩码；留空保存 = 保留原 Key（后端已支持）。
  const dbConfig = await configStore.fetchLLMConfig()
  if (dbConfig && dbConfig.id) {
    savedKeyMasked.value = dbConfig.api_key_masked || ''
    savedKeyOverwritten.value = !!dbConfig.api_key_masked
    const fmt: MessageFormat = (dbConfig.message_format as MessageFormat) || 'openai'
    const defaults = formatDefaults[fmt]
    config.value = {
      apiKey: '',
      baseUrl: dbConfig.base_url || defaults.baseUrl,
      messageFormat: fmt,
      modelName: dbConfig.model_name,
      temperature: dbConfig.temperature ?? 0.7,
      maxTokens: dbConfig.max_tokens ?? 2048,
      embeddingModel: dbConfig.embedding_model || 'shibing624/text2vec-base-chinese',
      embeddingDimension: dbConfig.embedding_dimension || 768
    }
  } else {
    const defaults = formatDefaults.openai
    config.value = {
      apiKey: '',
      baseUrl: defaults.baseUrl,
      messageFormat: 'openai',
      modelName: defaults.model,
      temperature: 0.7,
      maxTokens: 2048,
      embeddingModel: 'shibing624/text2vec-base-chinese',
      embeddingDimension: 768
    }
  }
})
</script>
