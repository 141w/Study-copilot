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

        <!-- AI 互动课堂配置 -->
        <div class="mt-6 pt-5 border-t border-[var(--border-default)]">
          <div class="flex items-center gap-2.5 mb-4">
            <div class="w-7 h-7 rounded-lg bg-[var(--color-primary-light)] flex items-center justify-center text-[var(--color-primary)]">
              <el-icon class="text-base"><MagicStick /></el-icon>
            </div>
            <h3 class="text-sm font-semibold text-[var(--text-primary)]">AI 互动课堂与多模态模型设置</h3>
          </div>

          <!-- 模块 1：专属图像生成模型 (解决主文本模型无法生图的问题) -->
          <div class="mb-4 p-4 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-default)]">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center gap-2">
                <span class="font-medium text-sm text-[var(--text-primary)]">专属图像生成模型 (Image Generation)</span>
                <span class="text-[11px] px-2 py-0.5 rounded bg-[var(--surface-card)] text-[var(--text-muted)] border border-[var(--border-default)]">
                  文生图能力
                </span>
              </div>
              <div class="flex items-center gap-2">
                <span class="text-xs text-[var(--text-muted)]">开启课件自动配图</span>
                <el-switch v-model="classroomForm.image_enabled" />
              </div>
            </div>

            <div v-show="classroomForm.image_enabled" class="space-y-4">
              <div class="grid grid-cols-1 md:grid-cols-2 gap-x-5 gap-y-4">
                <!-- 图像模型名称 -->
                <div>
                  <label class="block text-xs font-medium text-[var(--text-secondary)] mb-1.5">图像模型名称 (Model)</label>
                  <el-input v-model="classroomForm.image_model" placeholder="例如：black-forest-labs/FLUX.1-schnell 或 dall-e-3" />
                </div>

                <!-- 图像 API 地址 -->
                <div>
                  <label class="block text-xs font-medium text-[var(--text-secondary)] mb-1.5">图像接口地址 (Base URL)</label>
                  <el-input v-model="classroomForm.image_base_url" placeholder="例如：https://api.siliconflow.cn/v1" />
                </div>

                <!-- 图像 API Key -->
                <div>
                  <label class="block text-xs font-medium text-[var(--text-secondary)] mb-1.5">图像 API 密钥 (API Key)</label>
                  <el-input
                    v-model="classroomForm.image_api_key"
                    type="password"
                    show-password
                    :placeholder="savedImageKeyMasked ? `已保存: ${savedImageKeyMasked}` : '请输入文生图 API Key'"
                  />
                </div>

                <!-- 配图画幅比例 -->
                <div>
                  <label class="block text-xs font-medium text-[var(--text-secondary)] mb-1.5">预设配图尺寸 (Size)</label>
                  <el-select v-model="classroomForm.image_size" class="w-full">
                    <el-option value="1024x1024" label="1024x1024 (1:1 正方形)" />
                    <el-option value="1280x720" label="1280x720 (16:9 宽屏课件)" />
                    <el-option value="768x1024" label="768x1024 (3:4 书籍封面)" />
                  </el-select>
                </div>
              </div>

              <!-- 图像测试反馈 -->
              <transition name="el-fade-in">
                <div
                  v-if="imageTestResult"
                  class="p-3 rounded-xl text-xs flex items-start justify-between gap-3 border"
                  :class="imageTestResult.success ? 'bg-[var(--color-success-light)] border-[var(--color-success)] text-[var(--color-success)]' : 'bg-[var(--color-danger-light)] border-[var(--color-danger)] text-[var(--color-danger)]'"
                >
                  <div class="flex items-start gap-2">
                    <el-icon class="mt-0.5 text-base">
                      <CircleCheck v-if="imageTestResult.success" />
                      <WarningFilled v-else />
                    </el-icon>
                    <div>
                      <p class="font-medium">{{ imageTestResult.message }}</p>
                      <p v-if="imageTestResult.latency_ms" class="mt-0.5 text-[11px] opacity-80 font-mono">
                        响应延迟: {{ imageTestResult.latency_ms }}ms
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    class="opacity-60 hover:opacity-100 p-1"
                    @click="imageTestResult = null"
                  >
                    <el-icon><Close /></el-icon>
                  </button>
                </div>
              </transition>

              <!-- 图像连通性测试按钮 -->
              <div class="flex items-center gap-3 pt-1">
                <el-button
                  size="small"
                  :loading="testingImage"
                  @click="handleTestImage"
                >
                  <el-icon class="mr-1"><Promotion /></el-icon>测试生图接口
                </el-button>
              </div>
            </div>
          </div>

          <!-- 模块 2：课堂教学设计大模型 (Classroom LLM) -->
          <div class="p-4 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-default)]">
            <div class="flex items-center justify-between mb-3">
              <div>
                <div class="flex items-center gap-2">
                  <span class="font-medium text-sm text-[var(--text-primary)]">课堂教学大模型 (Teaching LLM)</span>
                  <span class="text-[11px] px-2 py-0.5 rounded bg-[var(--surface-card)] text-[var(--text-muted)] border border-[var(--border-default)]">
                    大纲与剧本编排
                  </span>
                </div>
                <p class="text-xs text-[var(--text-muted)] mt-1">
                  {{ classroomForm.use_custom_llm ? '使用独立自定义的教学设计大模型' : '默认复用上方的主问答大模型（省心免单独配置）' }}
                </p>
              </div>
              <el-radio-group v-model="classroomForm.use_custom_llm" size="small">
                <el-radio-button :value="false">复用主模型</el-radio-button>
                <el-radio-button :value="true">自定义模型</el-radio-button>
              </el-radio-group>
            </div>

            <div v-show="classroomForm.use_custom_llm" class="mt-4 pt-3 border-t border-[var(--border-default)] grid grid-cols-1 md:grid-cols-2 gap-x-5 gap-y-4">
              <div>
                <label class="block text-xs font-medium text-[var(--text-secondary)] mb-1.5">课堂模型名称 (Model)</label>
                <el-input v-model="classroomForm.classroom_llm_model" placeholder="例如：deepseek-chat 或 claude-3-5-sonnet" />
              </div>

              <div>
                <label class="block text-xs font-medium text-[var(--text-secondary)] mb-1.5">课堂 API 地址 (Base URL)</label>
                <el-input v-model="classroomForm.classroom_llm_base_url" placeholder="https://api.deepseek.com/v1" />
              </div>

              <div class="md:col-span-2">
                <label class="block text-xs font-medium text-[var(--text-secondary)] mb-1.5">课堂 API 密钥 (API Key)</label>
                <el-input
                  v-model="classroomForm.classroom_llm_api_key"
                  type="password"
                  show-password
                  :placeholder="savedClassroomLLMKeyMasked ? `已保存: ${savedClassroomLLMKeyMasked}` : '请输入专属课堂模型 API Key'"
                />
              </div>
            </div>
          </div>

          <!-- 模块 3：语音合成模型 (TTS / Voice Model) -->
          <div class="mt-4 p-4 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-default)]">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center gap-2">
                <span class="font-medium text-sm text-[var(--text-primary)]">语音合成模型 (TTS / Voice Model)</span>
                <span class="text-[11px] px-2 py-0.5 rounded bg-[var(--surface-card)] text-[var(--text-muted)] border border-[var(--border-default)]">
                  多角色原声演播
                </span>
              </div>
              <div class="flex items-center gap-2">
                <span class="text-xs text-[var(--text-muted)]">开启微课角色语音</span>
                <el-switch v-model="classroomForm.tts_enabled" />
              </div>
            </div>

            <div v-show="classroomForm.tts_enabled" class="space-y-4">
              <!-- 快捷预设按钮组 -->
              <div>
                <label class="block text-xs font-medium text-[var(--text-secondary)] mb-1.5">语音服务商预设 (Provider)</label>
                <div class="flex flex-wrap gap-2">
                  <button
                    type="button"
                    class="px-3 py-1.5 rounded-lg text-xs font-medium border transition-all"
                    :class="classroomForm.tts_provider === 'edge-tts' ? 'bg-[var(--color-primary)] text-white border-transparent' : 'bg-[var(--surface-card)] text-[var(--text-secondary)] border-[var(--border-default)] hover:border-[var(--color-primary)]'"
                    @click="selectTTSPreset('edge-tts')"
                  >
                    Microsoft Edge (内置免密·推荐)
                  </button>
                  <button
                    type="button"
                    class="px-3 py-1.5 rounded-lg text-xs font-medium border transition-all"
                    :class="classroomForm.tts_provider === 'custom' ? 'bg-[var(--color-primary)] text-white border-transparent' : 'bg-[var(--surface-card)] text-[var(--text-secondary)] border-[var(--border-default)] hover:border-[var(--color-primary)]'"
                    @click="selectTTSPreset('custom')"
                  >
                    自定义兼容端点
                  </button>
                </div>
              </div>

              <!-- 参数表单 -->
              <div v-if="classroomForm.tts_provider !== 'edge-tts'" class="grid grid-cols-1 md:grid-cols-2 gap-x-5 gap-y-4 pt-1">
                <div>
                  <label class="block text-xs font-medium text-[var(--text-secondary)] mb-1.5">语音模型名称 (Model)</label>
                  <el-input v-model="classroomForm.tts_model" placeholder="例如：tts-1 或 FunAudioLLM/CosyVoice2-0.5B" />
                </div>

                <div>
                  <label class="block text-xs font-medium text-[var(--text-secondary)] mb-1.5">语音 API 地址 (Base URL)</label>
                  <el-input v-model="classroomForm.tts_base_url" placeholder="https://api.openai.com/v1" />
                </div>

                <div class="md:col-span-2">
                  <label class="block text-xs font-medium text-[var(--text-secondary)] mb-1.5">语音 API 密钥 (API Key)</label>
                  <el-input
                    v-model="classroomForm.tts_api_key"
                    type="password"
                    show-password
                    :placeholder="savedTTSKeyMasked ? `已保存: ${savedTTSKeyMasked}` : '留空将自动复用主模型或默认 API Key'"
                  />
                </div>
              </div>

              <!-- 三大角色音色指派 -->
              <div class="pt-2 border-t border-[var(--border-default)]">
                <div class="text-xs font-semibold text-[var(--text-primary)] mb-2 flex items-center gap-1.5">
                  <el-icon><Reading /></el-icon>
                  <span>角色音色专属指派 (Character Voices)</span>
                  <span v-if="voiceOptionsSource" class="text-[10px] px-1.5 py-0.5 rounded font-normal" :class="voiceOptionsSourceClass">
                    {{ voiceOptionsSource }}
                  </span>
                </div>
                <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <!-- 苏老师 -->
                  <div class="p-3 rounded-lg bg-[var(--surface-card)] border border-[var(--border-default)]">
                    <div class="flex items-center gap-2 mb-1.5">
                      <span class="w-2 h-2 rounded-full bg-blue-500"></span>
                      <span class="text-xs font-medium text-[var(--text-primary)]">苏老师 (导师)</span>
                    </div>
                    <el-select
                      v-model="classroomForm.voice_teacher"
                      size="small"
                      class="w-full"
                      filterable
                      allow-create
                      default-first-option
                    >
                      <el-option
                        v-for="opt in teacherVoiceOptions"
                        :key="opt.value"
                        :value="opt.value"
                        :label="opt.label"
                      />
                    </el-select>
                  </div>

                  <!-- 求知同学 -->
                  <div class="p-3 rounded-lg bg-[var(--surface-card)] border border-[var(--border-default)]">
                    <div class="flex items-center gap-2 mb-1.5">
                      <span class="w-2 h-2 rounded-full bg-amber-500"></span>
                      <span class="text-xs font-medium text-[var(--text-primary)]">求知同学 (探索者)</span>
                    </div>
                    <el-select
                      v-model="classroomForm.voice_curious"
                      size="small"
                      class="w-full"
                      filterable
                      allow-create
                      default-first-option
                    >
                      <el-option
                        v-for="opt in curiousVoiceOptions"
                        :key="opt.value"
                        :value="opt.value"
                        :label="opt.label"
                      />
                    </el-select>
                  </div>

                  <!-- 学霸 -->
                  <div class="p-3 rounded-lg bg-[var(--surface-card)] border border-[var(--border-default)]">
                    <div class="flex items-center gap-2 mb-1.5">
                      <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
                      <span class="text-xs font-medium text-[var(--text-primary)]">学霸 (思考者)</span>
                    </div>
                    <el-select
                      v-model="classroomForm.voice_thinker"
                      size="small"
                      class="w-full"
                      filterable
                      allow-create
                      default-first-option
                    >
                      <el-option
                        v-for="opt in thinkerVoiceOptions"
                        :key="opt.value"
                        :value="opt.value"
                        :label="opt.label"
                      />
                    </el-select>
                  </div>
                </div>
              </div>

              <!-- 语音测试反馈 -->
              <transition name="el-fade-in">
                <div
                  v-if="ttsTestResult"
                  class="p-3 rounded-xl text-xs flex items-start justify-between gap-3 border"
                  :class="ttsTestResult.success ? 'bg-[var(--color-success-light)] border-[var(--color-success)] text-[var(--color-success)]' : 'bg-[var(--color-danger-light)] border-[var(--color-danger)] text-[var(--color-danger)]'"
                >
                  <div class="flex items-start gap-2">
                    <el-icon class="mt-0.5 text-base">
                      <CircleCheck v-if="ttsTestResult.success" />
                      <WarningFilled v-else />
                    </el-icon>
                    <div>
                      <p class="font-medium">{{ ttsTestResult.message }}</p>
                      <p v-if="ttsTestResult.latency_ms" class="mt-0.5 text-[11px] opacity-80 font-mono">
                        响应延迟: {{ ttsTestResult.latency_ms }}ms
                      </p>
                    </div>
                  </div>
                  <div class="flex items-center gap-2">
                    <el-button
                      v-if="ttsTestResult.audio_base64"
                      size="small"
                      type="success"
                      plain
                      @click="playPreviewAudio(ttsTestResult.audio_base64)"
                    >
                      <el-icon class="mr-1"><Reading /></el-icon>试听合成语音
                    </el-button>
                    <button
                      type="button"
                      class="opacity-60 hover:opacity-100 p-1"
                      @click="ttsTestResult = null"
                    >
                      <el-icon><Close /></el-icon>
                    </button>
                  </div>
                </div>
              </transition>

              <!-- 语音连通性测试按钮 -->
              <div class="flex items-center gap-3 pt-1">
                <el-button
                  size="small"
                  :loading="testingTTS"
                  @click="handleTestTTS"
                >
                  <el-icon class="mr-1"><Promotion /></el-icon>测试语音接口与试听
                </el-button>
              </div>
            </div>
          </div>
        </div>

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
  Close,
  MagicStick,
  Reading
} from '../components/icons'
import { useConfigStore } from '../stores/config'
import { useToastStore } from '../stores/toast'
import type { SystemStatus, LLMCapabilities, ImageTestResult, TTSTestResult } from '../types/models'

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

// ── AI 互动课堂与多模态模型专属状态 ──
const classroomForm = ref({
  use_custom_llm: false,
  classroom_llm_provider: 'openai',
  classroom_llm_model: '',
  classroom_llm_base_url: '',
  classroom_llm_api_key: '',
  image_enabled: true,
  image_provider: '',
  image_model: '',
  image_base_url: '',
  image_api_key: '',
  image_size: '1024x1024',
  tts_enabled: true,
  tts_provider: 'edge-tts',
  tts_model: 'tts-1',
  tts_base_url: 'https://api.openai.com/v1',
  tts_api_key: '',
  tts_speed: 1.0,
  voice_teacher: 'zh-CN-YunxiNeural',
  voice_curious: 'zh-CN-XiaoxiaoNeural',
  voice_thinker: 'zh-CN-YunjianNeural',
})

const savedImageKeyMasked = ref('')
const savedClassroomLLMKeyMasked = ref('')
const savedTTSKeyMasked = ref('')
const testingImage = ref(false)
const imageTestResult = ref<ImageTestResult | null>(null)
const testingTTS = ref(false)
const ttsTestResult = ref<TTSTestResult | null>(null)

function selectTTSPreset(provider: string): void {
  classroomForm.value.tts_provider = provider
  if (provider === 'edge-tts') {
    classroomForm.value.tts_model = 'edge-tts'
    classroomForm.value.tts_base_url = ''
    classroomForm.value.voice_teacher = 'zh-CN-YunxiNeural'
    classroomForm.value.voice_curious = 'zh-CN-XiaoxiaoNeural'
    classroomForm.value.voice_thinker = 'zh-CN-YunjianNeural'
  } else if (provider === 'custom') {
    classroomForm.value.tts_model = ''
    classroomForm.value.tts_base_url = ''
    classroomForm.value.voice_teacher = ''
    classroomForm.value.voice_curious = ''
    classroomForm.value.voice_thinker = ''
  }
}

// ── 音色选项（随服务商实时切换） ──
interface VoiceOption {
  value: string
  label: string
}

const edgeTTSVoices: VoiceOption[] = [
  { value: 'zh-CN-YunxiNeural',  label: 'zh-CN-YunxiNeural  (云希·男声·磁性)' },
  { value: 'zh-CN-XiaoxiaoNeural', label: 'zh-CN-XiaoxiaoNeural  (晓晓·女声·温柔)' },
  { value: 'zh-CN-YunjianNeural',  label: 'zh-CN-YunjianNeural  (云健·男声·沉稳)' },
  { value: 'zh-CN-YunyangNeural',  label: 'zh-CN-YunyangNeural  (云扬·男声·新闻)' },
  { value: 'zh-CN-XiaoyiNeural',   label: 'zh-CN-XiaoyiNeural  (晓伊·女声·亲切)' },
  { value: 'zh-CN-XiaochenNeural', label: 'zh-CN-XiaochenNeural  (晓辰·女声·活力)' },
  { value: 'zh-CN-XiaohanNeural',  label: 'zh-CN-XiaohanNeural  (晓涵·女声·甜美女)' },
  { value: 'zh-CN-XiaomengNeural', label: 'zh-CN-XiaomengNeural  (晓梦·女声·童声)' },
  { value: 'zh-CN-XiaomoNeural',   label: 'zh-CN-XiaomoNeural  (晓墨·女声·知性)' },
  { value: 'zh-CN-XiaoqiuNeural',  label: 'zh-CN-XiaoqiuNeural  (晓秋·女声·成熟)' },
  { value: 'zh-CN-XiaoruiNeural',  label: 'zh-CN-XiaoruiNeural  (晓睿·女声·理性)' },
  { value: 'zh-CN-XiaoshuangNeural', label: 'zh-CN-XiaoshuangNeural  (晓双·女声·童声)' },
  { value: 'zh-CN-XiaoxuanNeural', label: 'zh-CN-XiaoxuanNeural  (晓萱·女声·甜美女)' },
  { value: 'zh-CN-XiaoyanNeural',  label: 'zh-CN-XiaoyanNeural  (晓颜·女声·温暖)' },
  { value: 'zh-CN-XiaoyouNeural',  label: 'zh-CN-XiaoyouNeural  (晓悠·女声·闲聊)' },
  { value: 'zh-CN-XiaozhenNeural', label: 'zh-CN-XiaozhenNeural  (晓甄·女声·自然)' },
  { value: 'zh-CN-XiaochenMultilingual', label: 'zh-CN-XiaochenMultilingual  (晓辰·中英双语)' },
  { value: 'zh-CN-XiaohanMultilingual', label: 'zh-CN-XiaohanMultilingual  (晓涵·中英双语)' },
  { value: 'zh-CN-XiaomengMultilingual', label: 'zh-CN-XiaomengMultilingual  (晓梦·中英双语)' },
  { value: 'zh-CN-XiaomoMultilingual', label: 'zh-CN-XiaomoMultilingual  (晓墨·中英双语)' },
  { value: 'zh-CN-XiaoqiuMultilingual', label: 'zh-CN-XiaoqiuMultilingual  (晓秋·中英双语)' },
  { value: 'zh-CN-XiaoruiMultilingual', label: 'zh-CN-XiaoruiMultilingual  (晓睿·中英双语)' },
  { value: 'zh-CN-XiaoshuangMultilingual', label: 'zh-CN-XiaoshuangMultilingual  (晓双·中英双语)' },
  { value: 'zh-CN-XiaoxuanMultilingual', label: 'zh-CN-XiaoxuanMultilingual  (晓萱·中英双语)' },
  { value: 'zh-CN-XiaoyanMultilingual', label: 'zh-CN-XiaoyanMultilingual  (晓颜·中英双语)' },
]

const openAIVoices: VoiceOption[] = [
  { value: 'alloy', label: 'alloy  (中性·平衡)' },
  { value: 'echo',  label: 'echo  (男声·沉稳)' },
  { value: 'fable', label: 'fable  (英音·优雅)' },
  { value: 'onyx',  label: 'onyx  (男声·深沉)' },
  { value: 'nova',  label: 'nova  (女声·活力)' },
  { value: 'shimmer', label: 'shimmer  (女声·柔和)' },
]

const siliconflowVoices: VoiceOption[] = [
  { value: 'FunAudioLLM/CosyVoice2-0.5B:alex',    label: 'alex  (男声·英文)' },
  { value: 'FunAudioLLM/CosyVoice2-0.5B:anna',   label: 'anna  (女声·英文)' },
  { value: 'FunAudioLLM/CosyVoice2-0.5B:benjamin', label: 'benjamin  (男声·英文)' },
  { value: 'FunAudioLLM/CosyVoice2-0.5B:charles', label: 'charles  (男声·英文)' },
  { value: 'FunAudioLLM/CosyVoice2-0.5B:claire',  label: 'claire  (女声·英文)' },
  { value: 'FunAudioLLM/CosyVoice2-0.5B:david',   label: 'david  (男声·英文)' },
]

// 当前服务商对应的选项池（用于实时更新下拉列表）
const voiceOptionsSource = computed(() => {
  switch (classroomForm.value.tts_provider) {
    case 'edge-tts':      return 'Microsoft Edge TTS'
    case 'openai':        return 'OpenAI TTS'
    case 'siliconflow':   return 'SiliconFlow CosyVoice2'
    default:              return ''
  }
})

const voiceOptionsSourceClass = computed(() => {
  switch (classroomForm.value.tts_provider) {
    case 'edge-tts':      return 'bg-[var(--color-success-light)] text-[var(--color-success)]'
    case 'openai':        return 'bg-[var(--color-primary-light)] text-[var(--color-primary)]'
    case 'siliconflow':   return 'bg-[var(--color-primary-light)] text-[var(--color-primary)]'
    default:              return 'bg-[var(--bg-primary)] text-[var(--text-muted)]'
  }
})

const teacherVoiceOptions = computed((): VoiceOption[] => {
  switch (classroomForm.value.tts_provider) {
    case 'edge-tts':    return edgeTTSVoices
    case 'openai':      return openAIVoices
    case 'siliconflow': return siliconflowVoices
    default:            return []
  }
})

const curiousVoiceOptions = computed((): VoiceOption[] => {
  switch (classroomForm.value.tts_provider) {
    case 'edge-tts':    return edgeTTSVoices
    case 'openai':      return openAIVoices
    case 'siliconflow': return siliconflowVoices
    default:            return []
  }
})

const thinkerVoiceOptions = computed((): VoiceOption[] => {
  switch (classroomForm.value.tts_provider) {
    case 'edge-tts':    return edgeTTSVoices
    case 'openai':      return openAIVoices
    case 'siliconflow': return siliconflowVoices
    default:            return []
  }
})

function playPreviewAudio(b64: string): void {
  try {
    const audio = new Audio(b64)
    audio.play().catch((e) => console.error('Audio preview play failed:', e))
  } catch (e) {
    console.error('Failed to create audio preview:', e)
  }
}

async function handleTestTTS(): Promise<void> {
  testingTTS.value = true
  ttsTestResult.value = null
  try {
    const res = await configStore.testTTSConfig({
      tts_provider: classroomForm.value.tts_provider,
      tts_api_key: classroomForm.value.tts_api_key,
      tts_base_url: classroomForm.value.tts_base_url,
      tts_model: classroomForm.value.tts_model,
      voice_teacher: classroomForm.value.voice_teacher,
    })
    ttsTestResult.value = res
    if (res.success) {
      toast.success(res.message)
      if (res.audio_base64) {
        playPreviewAudio(res.audio_base64)
      }
    } else {
      toast.error(res.message || '语音接口测试失败')
    }
  } catch (err: any) {
    ttsTestResult.value = {
      success: false,
      message: err.message || '网络连接异常',
      audio_base64: null
    }
    toast.error(ttsTestResult.value.message)
  } finally {
    testingTTS.value = false
  }
}

async function handleTestImage(): Promise<void> {
  testingImage.value = true
  imageTestResult.value = null
  try {
    const res = await configStore.testImageConfig({
      image_provider: classroomForm.value.image_provider,
      image_api_key: classroomForm.value.image_api_key,
      image_base_url: classroomForm.value.image_base_url,
      image_model: classroomForm.value.image_model,
    })
    imageTestResult.value = res
    if (res.success) {
      toast.success(res.message)
    } else {
      toast.error(res.message || '生图接口测试失败')
    }
  } catch (err: any) {
    imageTestResult.value = {
      success: false,
      message: err.message || '网络连接异常'
    }
    toast.error(imageTestResult.value.message)
  } finally {
    testingImage.value = false
  }
}

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
      classroom_config: {
        use_custom_llm: classroomForm.value.use_custom_llm,
        classroom_llm_provider: classroomForm.value.classroom_llm_provider,
        classroom_llm_model: classroomForm.value.classroom_llm_model,
        classroom_llm_base_url: classroomForm.value.classroom_llm_base_url,
        classroom_llm_api_key: classroomForm.value.classroom_llm_api_key || undefined,
        image_enabled: classroomForm.value.image_enabled,
        image_provider: classroomForm.value.image_provider,
        image_model: classroomForm.value.image_model,
        image_base_url: classroomForm.value.image_base_url,
        image_api_key: classroomForm.value.image_api_key || undefined,
        image_size: classroomForm.value.image_size,
        tts_enabled: classroomForm.value.tts_enabled,
        tts_provider: classroomForm.value.tts_provider,
        tts_model: classroomForm.value.tts_model,
        tts_base_url: classroomForm.value.tts_base_url,
        tts_api_key: classroomForm.value.tts_api_key || undefined,
        tts_speed: classroomForm.value.tts_speed,
        voice_teacher: classroomForm.value.voice_teacher,
        voice_curious: classroomForm.value.voice_curious,
        voice_thinker: classroomForm.value.voice_thinker,
      },
    })
    const latest = await configStore.fetchLLMConfig()
    savedKeyMasked.value = latest?.api_key_masked || ''
    config.value.apiKey = ''
    savedKeyOverwritten.value = false

    if (latest?.classroom_config) {
      savedImageKeyMasked.value = latest.classroom_config.image_api_key_masked || ''
      savedClassroomLLMKeyMasked.value = latest.classroom_config.classroom_llm_api_key_masked || ''
      savedTTSKeyMasked.value = latest.classroom_config.tts_api_key_masked || ''
      classroomForm.value.image_api_key = ''
      classroomForm.value.classroom_llm_api_key = ''
      classroomForm.value.tts_api_key = ''
    }

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

  // 重置 AI 互动课堂表单
  classroomForm.value = {
    use_custom_llm: false,
    classroom_llm_provider: 'openai',
    classroom_llm_model: '',
    classroom_llm_base_url: '',
    classroom_llm_api_key: '',
    image_enabled: true,
    image_provider: '',
    image_model: '',
    image_base_url: '',
    image_api_key: '',
    image_size: '1024x1024',
    tts_enabled: true,
    tts_provider: 'edge-tts',
    tts_model: 'tts-1',
    tts_base_url: 'https://api.openai.com/v1',
    tts_api_key: '',
    tts_speed: 1.0,
    voice_teacher: 'zh-CN-YunxiNeural',
    voice_curious: 'zh-CN-XiaoxiaoNeural',
    voice_thinker: 'zh-CN-YunjianNeural',
  }
  imageTestResult.value = null
  ttsTestResult.value = null

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

    if (dbConfig.classroom_config) {
      const cc = dbConfig.classroom_config
      classroomForm.value.use_custom_llm = !!cc.use_custom_llm
      classroomForm.value.classroom_llm_provider = cc.classroom_llm_provider || 'openai'
      classroomForm.value.classroom_llm_model = cc.classroom_llm_model || ''
      classroomForm.value.classroom_llm_base_url = cc.classroom_llm_base_url || ''
      classroomForm.value.image_enabled = cc.image_enabled !== false
      classroomForm.value.image_provider = cc.image_provider || ''
      classroomForm.value.image_model = cc.image_model || ''
      classroomForm.value.image_base_url = cc.image_base_url || ''
      classroomForm.value.image_size = cc.image_size || '1024x1024'
      savedImageKeyMasked.value = cc.image_api_key_masked || ''
      savedClassroomLLMKeyMasked.value = cc.classroom_llm_api_key_masked || ''

      classroomForm.value.tts_enabled = cc.tts_enabled !== false
      classroomForm.value.tts_provider = cc.tts_provider || 'edge-tts'
      classroomForm.value.tts_model = cc.tts_model || 'tts-1'
      classroomForm.value.tts_base_url = cc.tts_base_url || 'https://api.openai.com/v1'
      classroomForm.value.tts_speed = cc.tts_speed || 1.0
      classroomForm.value.voice_teacher = cc.voice_teacher || 'zh-CN-YunxiNeural'
      classroomForm.value.voice_curious = cc.voice_curious || 'zh-CN-XiaoxiaoNeural'
      classroomForm.value.voice_thinker = cc.voice_thinker || 'zh-CN-YunjianNeural'
      savedTTSKeyMasked.value = cc.tts_api_key_masked || ''
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
