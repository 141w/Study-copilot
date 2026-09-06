<template>
  <div class="max-w-4xl mx-auto px-6 py-8">
    <!-- 顶部导航与标题 -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
      <div>
        <div class="flex items-center gap-3">
          <h1 class="text-2xl font-bold text-[var(--text-primary)]">模型配置</h1>
          <span class="text-xs px-2.5 py-0.5 rounded-full bg-[var(--color-primary-light)] text-[var(--color-primary)] font-medium">
            AI Settings
          </span>
        </div>
        <p class="text-sm text-[var(--text-muted)] mt-1.5">
          配置大语言模型 (LLM) 服务商、密钥与推理参数
        </p>
      </div>
      <div class="flex items-center gap-2.5">
        <router-link to="/chat">
          <el-button>
            <el-icon class="mr-1"><ChatDotSquare /></el-icon>返回问答
          </el-button>
        </router-link>
      </div>
    </div>

    <!-- LLM 参数配置表单 -->
    <div class="card p-6 mb-6">
      <div class="flex items-center justify-between pb-4 mb-6 border-b border-[var(--border-default)]">
        <h2 class="text-base font-semibold text-[var(--text-primary)]">大语言模型参数 (LLM)</h2>
        <span class="text-xs px-2 py-0.5 rounded bg-[var(--bg-secondary)] text-[var(--text-secondary)] border border-[var(--border-default)]">
          {{ config.messageFormat.toUpperCase() }} 协议
        </span>
      </div>

      <el-form ref="formRef" :model="config" :rules="formRules" label-position="top">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-5">
          <!-- 消息格式 -->
          <el-form-item label="接口协议格式" prop="messageFormat">
            <el-select v-model="config.messageFormat" class="w-full" @change="onFormatChange">
              <el-option value="openai" label="OpenAI 兼容协议" />
              <el-option value="anthropic" label="Anthropic 协议" />
              <el-option value="gemini" label="Gemini 协议" />
              <el-option value="ollama" label="Ollama 本地协议" />
            </el-select>
          </el-form-item>

          <!-- 模型名称 -->
          <el-form-item label="模型名称 (Model Name)" prop="modelName">
            <el-input v-model="config.modelName" placeholder="例如：deepseek-chat / gpt-4o-mini" />
          </el-form-item>

          <!-- Base URL -->
          <el-form-item label="API 地址 (Base URL)" prop="baseUrl">
            <el-input v-model="config.baseUrl" placeholder="https://api.openai.com/v1" />
          </el-form-item>

          <!-- API Key -->
          <el-form-item label="API 密钥 (API Key)">
            <el-input
              v-model="config.apiKey"
              type="password"
              show-password
              :placeholder="savedKeyMasked ? `已保存: ${savedKeyMasked}` : '请输入 API Key'"
            />
          </el-form-item>

          <!-- 采样温度 -->
          <el-form-item label="采样温度 (Temperature)">
            <div class="flex items-center gap-4 w-full px-1">
              <el-slider
                v-model="config.temperature"
                :min="0"
                :max="1"
                :step="0.05"
                class="flex-1"
              />
              <span class="text-xs font-mono w-8 text-right text-[var(--color-primary)] font-semibold">{{ config.temperature }}</span>
            </div>
          </el-form-item>

          <!-- 单次最大生成 -->
          <el-form-item label="单次最大生成 (Max Output Tokens)">
            <el-input
              v-model="config.maxTokens"
              placeholder="默认 8192（可不填，自动使用厂商值）"
              clearable
            />
          </el-form-item>

          <!-- 上下文窗口容量 -->
          <el-form-item label="上下文窗口 (Context Window)" class="md:col-span-2">
            <el-input
              v-model="config.contextWindow"
              placeholder="默认 262144（256k，可不填，自动使用厂商值）"
              clearable
            />
          </el-form-item>
        </div>

        <!-- 连通性测试反馈条 -->
        <transition name="el-fade-in">
          <div
            v-if="testResult"
            class="mt-5 p-3.5 rounded-xl text-xs flex items-start justify-between gap-3 border"
            :class="testResult.success ? 'bg-[var(--color-success-light)] border-[var(--color-success)] text-[var(--color-success)]' : 'bg-[var(--color-danger-light)] border-[var(--color-danger)] text-[var(--color-danger)]'"
          >
            <div class="flex items-start gap-2">
              <el-icon class="mt-0.5 text-base">
                <CircleCheck v-if="testResult.success" />
                <WarningFilled v-else />
              </el-icon>
              <div>
                <p class="font-medium">{{ testResult.message }}</p>
                <p v-if="testResult.reply" class="mt-1 text-[11px] opacity-80 font-mono">
                  模型返回响应: "{{ testResult.reply }}"
                </p>
              </div>
            </div>
            <button
              type="button"
              class="opacity-60 hover:opacity-100 p-1"
              @click="testResult = null"
            >
              <el-icon><Close /></el-icon>
            </button>
          </div>
        </transition>

        <!-- 按钮操作栏 -->
        <div class="mt-6 pt-5 border-t border-[var(--border-default)] flex items-center justify-between gap-3">
          <div class="flex items-center gap-3">
            <el-button
              type="primary"
              :loading="saving"
              @click="saveConfig"
            >
              保存配置
            </el-button>
            <el-button
              :loading="testingConnection"
              @click="handleTestConnection"
            >
              <el-icon class="mr-1"><Promotion /></el-icon>测试连通性
            </el-button>
          </div>
          <el-button text @click="resetConfig">重置为默认值</el-button>
        </div>
      </el-form>
    </div>

    <!-- ── 底层状态与规格探测 ── -->
    <div class="card p-6 bg-[var(--surface-card)]">
      <div class="flex items-center justify-between pb-4 mb-5 border-b border-[var(--border-default)]">
        <div class="flex items-center gap-2.5">
          <div class="w-8 h-8 rounded-lg bg-[var(--color-primary-light)] flex items-center justify-center text-[var(--color-primary)]">
            <el-icon class="text-lg"><Brain /></el-icon>
          </div>
          <h2 class="text-base font-semibold text-[var(--text-primary)]">模型规格检测与引擎状态</h2>
        </div>
        <div class="flex items-center gap-2">
          <el-button
            size="small"
            :loading="detectingCaps"
            @click="handleDetectCaps"
          >
            <el-icon class="mr-1"><Lightning /></el-icon>探测规格
          </el-button>
          <el-button
            size="small"
            :loading="loadingStatus"
            @click="loadSystemStatus"
          >
            <el-icon class="mr-1"><Switch /></el-icon>刷新状态
          </el-button>
        </div>
      </div>

      <!-- 状态卡片 -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
        <!-- 卡片 1: 上下文窗口 -->
        <div class="p-3.5 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-default)]">
          <div class="flex items-center justify-between">
            <span class="text-xs text-[var(--text-muted)]">上下文窗口</span>
            <span v-if="capsSourceTag" class="text-[10px] px-1.5 py-0.5 rounded font-medium" :class="capsSourceClass">
              {{ capsSourceTag }}
            </span>
          </div>
          <div class="text-base font-bold text-[var(--color-primary)] mt-1.5">
            {{ formatTokenCount(displayContextWindow) }}
            <span class="text-xs font-normal text-[var(--text-muted)]">({{ displayContextWindow.toLocaleString() }} tokens)</span>
          </div>
        </div>

        <!-- 卡片 2: 最大输出 & 延迟 -->
        <div class="p-3.5 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-default)]">
          <div class="flex items-center justify-between">
            <span class="text-xs text-[var(--text-muted)]">单次最大生成</span>
            <span v-if="llmLatency !== null" class="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-success-light)] text-[var(--color-success)] font-mono">
              {{ llmLatency }}ms
            </span>
          </div>
          <div class="text-base font-bold text-[var(--text-primary)] mt-1.5">
            {{ displayMaxTokens.toLocaleString() }}
            <span class="text-xs font-normal text-[var(--text-muted)]">tokens</span>
          </div>
        </div>

        <!-- 卡片 3: 知识库切片数 -->
        <div class="p-3.5 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-default)]">
          <span class="text-xs text-[var(--text-muted)]">知识库已切片</span>
          <div class="text-base font-bold text-[var(--text-primary)] mt-1.5">
            {{ systemStatus?.database?.document_chunks ?? 0 }}
            <span class="text-xs font-normal text-[var(--text-muted)]">chunks</span>
          </div>
        </div>

        <!-- 卡片 4: 向量引擎状态 -->
        <div class="p-3.5 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-default)]">
          <div class="flex items-center justify-between">
            <span class="text-xs text-[var(--text-muted)]">向量引擎</span>
            <span class="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-success-light)] text-[var(--color-success)] font-medium">
              768维
            </span>
          </div>
          <div class="text-sm font-bold text-[var(--text-primary)] mt-1.5 truncate">
            {{ systemStatus?.vector_engine?.device || '本地设备' }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import {
  ChatDotSquare,
  Lightning,
  Promotion,
  Brain,
  Switch,
  CircleCheck,
  WarningFilled,
  Close
} from '../components/icons'
import { useConfigStore } from '../stores/config'
import { useToastStore } from '../stores/toast'
import type { SystemStatus, LLMCapabilities } from '../types/models'

type MessageFormat = 'openai' | 'anthropic' | 'gemini' | 'ollama'

interface ModelConfigForm {
  apiKey: string
  baseUrl: string
  messageFormat: MessageFormat
  modelName: string
  temperature: number
  maxTokens: string | number
  contextWindow: string | number
}

const configStore = useConfigStore()
const toast = useToastStore()

const formRef = ref<FormInstance | null>(null)
const saving = ref(false)
const testingConnection = ref(false)
const testResult = ref<{ success: boolean; message: string; reply?: string } | null>(null)

// 探测与状态
const detectingCaps = ref(false)
const detectedCaps = ref<LLMCapabilities | null>(null)
const llmLatency = ref<number | null>(null)
const loadingStatus = ref(false)
const systemStatus = ref<SystemStatus | null>(null)

const config = ref<ModelConfigForm>({
  apiKey: '',
  baseUrl: 'https://api.openai.com/v1',
  messageFormat: 'openai',
  modelName: 'gpt-4o-mini',
  temperature: 0.7,
  maxTokens: '',
  contextWindow: '',
})

// 表单校验规则
const formRules: FormRules = {
  messageFormat: [{ required: true, message: '请选择接口协议格式', trigger: 'change' }],
  modelName: [{ required: true, message: '请输入模型名称', trigger: 'blur' }],
  baseUrl: [{ required: true, message: '请输入 API 地址', trigger: 'blur' }],
}

// 已保存 Key 的掩码展示值
const savedKeyMasked = ref('')
const savedKeyOverwritten = ref(false)

// 规格来源标签
const capsSourceTag = computed(() => {
  if (!detectedCaps.value) return ''
  switch (detectedCaps.value.source) {
    case 'vendor_api': return '厂商返回'
    case 'vendor_spec': return '厂商规格'
    case 'default_256k': return '默认 256k'
    default: return ''
  }
})

const capsSourceClass = computed(() => {
  if (!detectedCaps.value) return ''
  switch (detectedCaps.value.source) {
    case 'vendor_api': return 'bg-[var(--color-success-light)] text-[var(--color-success)]'
    case 'vendor_spec': return 'bg-[var(--color-primary-light)] text-[var(--color-primary)]'
    default: return 'bg-[var(--bg-primary)] text-[var(--text-muted)]'
  }
})

const displayContextWindow = computed(() => {
  if (config.value.contextWindow !== '' && config.value.contextWindow != null) {
    return Number(config.value.contextWindow) || 262144
  }
  return detectedCaps.value?.context_window || 262144
})

const displayMaxTokens = computed(() => {
  if (config.value.maxTokens !== '' && config.value.maxTokens != null) {
    return Number(config.value.maxTokens) || 8192
  }
  return detectedCaps.value?.max_output_tokens || 8192
})

function formatTokenCount(tokens: number): string {
  if (!tokens) return '256k'
  if (tokens >= 1048576) {
    const m = tokens / 1048576
    return Number.isInteger(m) ? `${m}M` : `${m.toFixed(1)}M`
  }
  if (tokens >= 1024) {
    return `${Math.round(tokens / 1024)}k`
  }
  return `${tokens}`
}

// 默认协议配置
const formatDefaults: Record<MessageFormat, { baseUrl: string; model: string }> = {
  openai:    { baseUrl: 'https://api.openai.com/v1',            model: 'gpt-4o-mini' },
  anthropic: { baseUrl: 'https://api.anthropic.com',              model: 'claude-3-5-sonnet-20241022' },
  gemini:    { baseUrl: 'https://generativelanguage.googleapis.com/v1', model: 'gemini-1.5-flash-latest' },
  ollama:    { baseUrl: 'http://localhost:11434/v1',              model: 'qwen2.5:7b' },
}

function onFormatChange(): void {
  const defaults = formatDefaults[config.value.messageFormat]
  if (defaults && !savedKeyOverwritten.value) {
    config.value.baseUrl = defaults.baseUrl
    config.value.modelName = defaults.model
  }
}

async function handleDetectCaps(): Promise<void> {
  detectingCaps.value = true
  try {
    const caps = await configStore.detectLLMCapabilities({
      provider: config.value.messageFormat,
      api_key: config.value.apiKey,
      base_url: config.value.baseUrl,
      model_name: config.value.modelName,
      message_format: config.value.messageFormat,
    })
    if (caps) {
      detectedCaps.value = caps
      if (caps.latency_ms !== undefined) {
        llmLatency.value = caps.latency_ms
      }
      toast.success(`探测完成：${caps.model_name}（${formatTokenCount(caps.context_window)}）`)
    } else {
      toast.warning('未能探测到模型规格，将使用默认值')
    }
  } catch (err: any) {
    toast.error('探测失败：' + (err.message || '网络错误'))
  } finally {
    detectingCaps.value = false
  }
}

async function loadSystemStatus(): Promise<void> {
  loadingStatus.value = true
  try {
    const status = await configStore.getSystemStatus()
    if (status) {
      systemStatus.value = status
    }
  } catch (err) {
    console.error('Failed to load system status:', err)
  } finally {
    loadingStatus.value = false
  }
}

async function handleTestConnection(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  testingConnection.value = true
  testResult.value = null
  try {
    const res = await configStore.testLLMConfig({
      provider: config.value.messageFormat,
      api_key: config.value.apiKey,
      base_url: config.value.baseUrl,
      model_name: config.value.modelName,
      message_format: config.value.messageFormat,
    })
    testResult.value = res
    if (res.latency_ms !== undefined) {
      llmLatency.value = res.latency_ms
    }
    if (res.capabilities) {
      detectedCaps.value = res.capabilities
    }
    if (res.success) {
      toast.success(`连通性测试通过！(${res.latency_ms ?? 0}ms)`)
    } else {
      toast.error('连通性测试失败，请查看详情')
    }
  } catch (err: any) {
    testResult.value = {
      success: false,
      message: err.message || '网络请求错误'
    }
  } finally {
    testingConnection.value = false
  }
}

async function saveConfig(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    const maxTokensNum = config.value.maxTokens !== '' && config.value.maxTokens != null
      ? Number(config.value.maxTokens)
      : undefined
    const contextWinNum = config.value.contextWindow !== '' && config.value.contextWindow != null
      ? Number(config.value.contextWindow)
      : undefined

    await configStore.saveLLMConfig({
      provider: config.value.messageFormat,
      api_key: config.value.apiKey,
      base_url: config.value.baseUrl,
      model_name: config.value.modelName,
      temperature: config.value.temperature,
      max_tokens: maxTokensNum,
      context_window: contextWinNum,
      embedding_model: 'shibing624/text2vec-base-chinese',
      embedding_dimension: 768,
      message_format: config.value.messageFormat,
    })
    const latest = await configStore.fetchLLMConfig()
    savedKeyMasked.value = latest?.api_key_masked || ''
    config.value.apiKey = ''
    savedKeyOverwritten.value = false
    toast.success('配置已保存')
  } catch (error) {
    toast.error('保存失败：' + ((error as Error).message || '未知错误'))
  } finally {
    saving.value = false
  }
}

function resetConfig(): void {
  const defaults = formatDefaults.openai
  config.value = {
    apiKey: '',
    baseUrl: defaults.baseUrl,
    messageFormat: 'openai',
    modelName: defaults.model,
    temperature: 0.7,
    maxTokens: '',
    contextWindow: '',
  }
  savedKeyOverwritten.value = false
  testResult.value = null
  detectedCaps.value = null
  llmLatency.value = null
  formRef.value?.clearValidate()
  toast.info('已重置为默认值（尚未保存）')
}

onMounted(async () => {
  loadSystemStatus()
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
      maxTokens: dbConfig.max_tokens ?? '',
      contextWindow: dbConfig.context_window ?? '',
    }
  } else {
    const defaults = formatDefaults.openai
    config.value = {
      apiKey: '',
      baseUrl: defaults.baseUrl,
      messageFormat: 'openai',
      modelName: defaults.model,
      temperature: 0.7,
      maxTokens: '',
      contextWindow: '',
    }
  }
})
</script>
