<template>
  <div
    ref="playerContainer"
    class="h-screen max-h-screen overflow-hidden bg-[var(--bg-primary)] text-[var(--text-primary)] flex flex-col select-none relative font-sans"
  >
    <!-- 顶栏导航与快捷控制条 (Clean Studio Header) -->
    <header class="h-14 px-3 sm:px-6 bg-[var(--surface-card)]/90 backdrop-blur-md border-b border-[var(--border-default)] flex items-center justify-between z-20 flex-shrink-0 shadow-xs">
      <!-- 左侧：返回课程、微课标识、标题与幕进度 -->
      <div class="flex items-center gap-2.5 sm:gap-3 min-w-0">
        <el-button
          circle
          size="small"
          @click="goBack"
          title="返回"
        >
          <el-icon><ArrowLeft /></el-icon>
        </el-button>
        <div class="min-w-0 flex items-center gap-2 sm:gap-2.5">
          <span class="text-[11px] px-2.5 py-0.5 rounded-full bg-[var(--color-primary)]/10 text-[var(--color-primary)] font-semibold flex-shrink-0 border border-[var(--color-primary)]/20">
            AI 互动微课
          </span>
          <h1 class="text-xs sm:text-sm font-semibold truncate text-[var(--text-primary)] max-w-[140px] sm:max-w-xs md:max-w-md" :title="courseTitle">
            {{ courseTitle }}
          </h1>
          <span class="text-xs text-[var(--text-muted)] font-mono hidden sm:inline-block border-l border-[var(--border-default)] pl-2.5">
            第 {{ currentSceneIndex + 1 }} / {{ totalScenes }} 幕
          </span>
          <span
            v-if="sourceDocuments.length > 0"
            class="text-[11px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 font-medium hidden md:inline-flex items-center gap-1 border border-emerald-500/20"
          >
            <el-icon class="w-3 h-3"><Tickets /></el-icon>
            {{ sourceDocuments.length }} 份参考文档
          </span>
        </div>
      </div>

      <!-- 右侧控制组：倍速、语音、连播、台词记录、目录与全屏 -->
      <div class="flex items-center gap-1.5 sm:gap-2">
        <!-- 倍速切换 -->
        <el-button
          size="small"
          @click="cyclePlaybackRate"
          title="点击切换播放倍速"
        >
          <span class="text-xs font-mono font-medium">{{ playbackRate }}x</span>
        </el-button>

        <!-- 语音朗读开关 -->
        <el-button
          size="small"
          :type="audioEnabled ? 'primary' : 'default'"
          plain
          @click="toggleAudio"
          :title="audioEnabled ? '语音朗读已开启' : '语音朗读已静音'"
        >
          <el-icon><Reading /></el-icon>
          <span class="text-xs ml-1 hidden md:inline">{{ audioEnabled ? '语音开启' : '已静音' }}</span>
        </el-button>

        <!-- 自动连播开关 -->
        <el-button
          size="small"
          :type="autoAdvance ? 'primary' : 'default'"
          plain
          @click="autoAdvance = !autoAdvance"
          :title="autoAdvance ? '自动切幕已开启' : '手动切幕'"
          class="hidden sm:inline-flex"
        >
          <el-icon><Promotion /></el-icon>
          <span class="text-xs ml-1 hidden lg:inline">{{ autoAdvance ? '自动连播' : '单幕暂停' }}</span>
        </el-button>

        <!-- 研讨台词记录抽屉 -->
        <el-button
          circle
          size="small"
          @click="showHistoryDrawer = true"
          title="台词记录"
        >
          <el-icon><ChatLineRound /></el-icon>
        </el-button>

        <!-- 章节目录抽屉切换 -->
        <el-button
          circle
          size="small"
          :type="showSidebar ? 'primary' : 'default'"
          @click="showSidebar = !showSidebar"
          title="章节目录"
        >
          <el-icon><List /></el-icon>
        </el-button>

        <!-- 全屏按钮 -->
        <el-button
          circle
          size="small"
          @click="toggleFullscreen"
          title="全屏切换"
        >
          <el-icon><Fold /></el-icon>
        </el-button>
      </div>
    </header>

    <!-- 加载中态 -->
    <div v-if="loading" class="flex-1 flex flex-col items-center justify-center p-8 space-y-4">
      <el-icon class="text-4xl text-[var(--color-primary)] reicon-spin"><Loading /></el-icon>
      <p class="text-sm text-[var(--text-muted)] animate-pulse">正在加载 AI 互动课堂课件与剧本...</p>
    </div>

    <!-- 错误/未找到态 -->
    <div v-else-if="error || !classroomData" class="flex-1 flex flex-col items-center justify-center p-8 space-y-4">
      <div class="w-16 h-16 rounded-2xl bg-[var(--color-warning)]/10 flex items-center justify-center text-[var(--color-warning)] mb-2">
        <el-icon class="text-3xl"><CircleCloseFilled /></el-icon>
      </div>
      <h2 class="text-lg font-medium text-[var(--text-primary)]">课件未找到或已被移除</h2>
      <p class="text-sm text-[var(--text-muted)] max-w-md text-center">
        {{ error || '当前课程暂未生成完整的互动微课，请前往课程详情页点击“生成课堂”。' }}
      </p>
      <div class="flex items-center gap-3 mt-4">
        <el-button type="primary" @click="goBack">返回课程详情</el-button>
        <el-button @click="loadData">重试加载</el-button>
      </div>
    </div>

    <!-- 主演播视口 (Visual Stage + Studio Deck) -->
    <div v-else class="flex-1 flex overflow-hidden relative min-h-0">
      <main class="flex-1 flex flex-col items-center justify-between p-3 sm:p-4 overflow-hidden relative min-h-0">
        <!-- 16:9 画布纯净演播区 (Visual Stage - 100% 内容无遮挡) -->
        <div class="w-full max-w-5xl flex-1 flex flex-col justify-center items-center min-h-0 relative">
          <div
            class="relative w-full aspect-video rounded-2xl overflow-hidden border border-[var(--border-default)] shadow-lg flex flex-col justify-center transition-all duration-300"
            :style="{
              maxHeight: 'min(560px, calc(100vh - 250px))',
              maxWidth: 'calc((100vh - 250px) * 16 / 9)',
              backgroundColor: canvasTheme.backgroundColor || 'var(--surface-card)',
              color: canvasTheme.fontColor || 'var(--text-primary)'
            }"
          >
            <!-- 幕顶微型信息栏 -->
            <div class="absolute top-3 left-4 right-4 flex items-center justify-between pointer-events-none z-10">
              <div class="flex items-center gap-2">
                <span class="text-[11px] px-2.5 py-0.5 rounded-full font-semibold bg-black/40 backdrop-blur-md text-white border border-white/10 shadow-xs">
                  {{ currentScene?.type === 'quiz' ? '随堂交互测验' : `第 ${currentSceneIndex + 1} 幕 · 讲解` }}
                </span>
                <span class="text-xs text-white/80 font-medium truncate max-w-md drop-shadow">
                  {{ currentScene?.title }}
                </span>
              </div>
              <div class="text-[11px] text-white/60 font-mono bg-black/30 backdrop-blur px-2 py-0.5 rounded-md border border-white/10">
                Scene {{ currentSceneIndex + 1 }} / {{ totalScenes }}
              </div>
            </div>

            <!-- A. Slide 场景渲染器 (PPTist 16:9 坐标系) -->
            <div
              v-if="currentScene?.type === 'slide'"
              class="relative w-full h-full p-6 sm:p-8 overflow-hidden select-none"
            >
              <div
                v-for="el in canvasElements"
                :key="el.id"
                class="absolute transition-all duration-300 flex flex-col justify-center"
                :style="getElementStyle(el)"
              >
                <!-- 文本元素 -->
                <template v-if="el.type === 'text'">
                  <div
                    class="font-semibold leading-tight tracking-wide drop-shadow-xs"
                    :style="{
                      fontSize: `clamp(13px, ${(el.fontSize || 20) / 10}vw, ${el.fontSize || 24}px)`,
                      color: el.defaultColor || 'inherit'
                    }"
                  >
                    {{ el.content }}
                  </div>
                </template>

                <!-- 图片元素（概念插图） -->
                <template v-else-if="el.type === 'image'">
                  <div class="w-full h-full rounded-xl overflow-hidden shadow-md border border-[var(--border-default)] relative group bg-black/20">
                    <img
                      :src="el.src"
                      alt="Illustration"
                      class="w-full h-full object-cover"
                    />
                  </div>
                </template>

                <!-- 图形/卡片容器元素 -->
                <template v-else-if="el.type === 'shape'">
                  <div
                    class="w-full h-full rounded-xl p-4 sm:p-5 shadow-xs border transition-all duration-300 flex flex-col overflow-hidden backdrop-blur-sm"
                    :class="[
                      isElementHighlighted(el.id)
                        ? 'ring-2 ring-[var(--color-primary)] border-[var(--color-primary)] bg-[var(--color-primary-light)]/20 scale-[1.01] shadow-md'
                        : 'border-[var(--border-default)]'
                    ]"
                    :style="{
                      backgroundColor: el.fill || 'var(--bg-secondary)',
                      borderColor: el.outline?.color || 'var(--border-default)'
                    }"
                  >
                    <div
                      class="text-xs sm:text-sm whitespace-pre-wrap leading-relaxed overflow-y-auto"
                      :style="{ color: el.fill?.startsWith('#F') || el.fill?.startsWith('#E') || el.fill?.startsWith('#fff') ? '#1E293B' : 'inherit' }"
                    >
                      {{ el.text }}
                    </div>
                  </div>
                </template>
              </div>
            </div>

            <!-- B. Quiz 交互测验场景渲染器 -->
            <div
              v-else-if="currentScene?.type === 'quiz'"
              class="relative w-full h-full p-6 sm:p-10 flex flex-col justify-center max-w-2xl mx-auto overflow-y-auto"
            >
              <div class="mb-3">
                <span class="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-[var(--color-primary)]/15 text-[var(--color-primary)] border border-[var(--color-primary)]/20">
                  随堂挑战
                </span>
                <h2 class="text-sm sm:text-lg font-bold mt-2.5 text-[var(--text-primary)] leading-snug">
                  {{ currentQuiz?.question }}
                </h2>
              </div>

              <!-- 选项列表 -->
              <div class="space-y-2.5 my-1">
                <button
                  v-for="(opt, oIdx) in currentQuizOptions"
                  :key="oIdx"
                  @click="selectQuizOption(opt)"
                  :disabled="quizSubmitted"
                  class="w-full text-left p-3 rounded-xl border text-xs sm:text-sm font-medium transition-all duration-200 flex items-center justify-between cursor-pointer"
                  :class="getQuizOptionClass(opt)"
                >
                  <div class="flex items-center gap-2.5">
                    <span class="w-6 h-6 rounded-full flex items-center justify-center font-bold text-xs" :class="getQuizOptionBadgeClass(opt)">
                      {{ getOptionLetter(Number(oIdx)) }}
                    </span>
                    <span class="leading-normal">{{ opt }}</span>
                  </div>
                  <el-icon v-if="quizSubmitted && isOptionCorrect(opt)" class="text-[var(--color-success)] text-base"><CircleCheckFilled /></el-icon>
                  <el-icon v-else-if="quizSubmitted && selectedOption === opt && !isOptionCorrect(opt)" class="text-[var(--color-error)] text-base"><CircleCloseFilled /></el-icon>
                </button>
              </div>

              <!-- 测验解析与反馈 -->
              <div v-if="quizSubmitted" class="mt-3 p-3.5 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-default)]">
                <div class="flex items-center gap-2 mb-1.5">
                  <span class="text-xs font-bold" :class="isCurrentAnswerCorrect ? 'text-[var(--color-success)]' : 'text-[var(--color-error)]'">
                    {{ isCurrentAnswerCorrect ? '✓ 回答正确！' : '✗ 回答有误' }}
                  </span>
                  <span class="text-xs text-[var(--text-secondary)]">正确答案是：{{ currentQuiz?.answer }}</span>
                </div>
                <p v-if="currentQuiz?.explanation" class="text-xs text-[var(--text-muted)] leading-relaxed">
                  💡 {{ currentQuiz.explanation }}
                </p>
                <div class="mt-2.5 flex justify-end">
                  <el-button
                    type="primary"
                    size="small"
                    @click="nextScene"
                    class="!px-3.5"
                  >
                    进入下一幕
                  </el-button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 课堂互动台词与控制总台 (Studio Deck - 位于画布下方，完全解耦不遮挡) -->
        <div class="w-full max-w-5xl flex flex-col gap-2.5 mt-2 flex-shrink-0">
          <!-- 上层：当前发言角色与剧本台词卡 -->
          <div class="w-full rounded-2xl bg-[var(--surface-card)] border border-[var(--border-default)] px-4 py-2.5 sm:py-3 shadow-xs flex items-center gap-3.5 transition-colors">
            <!-- 角色头像与徽章 -->
            <div class="flex items-center gap-2.5 flex-shrink-0">
              <div
                class="w-9 h-9 sm:w-10 sm:h-10 rounded-xl flex items-center justify-center flex-shrink-0 transition-transform duration-300 relative shadow-xs"
                :style="{
                  backgroundColor: currentAgentConfig?.color ? `${currentAgentConfig.color}15` : 'rgba(59, 130, 246, 0.12)',
                  color: currentAgentConfig?.color || '#3B82F6',
                  border: `1px solid ${currentAgentConfig?.color ? `${currentAgentConfig.color}35` : 'rgba(59, 130, 246, 0.25)'}`
                }"
              >
                <el-icon class="text-lg">
                  <GraduationCap v-if="currentAgentConfig?.id === 'teacher'" />
                  <Brain v-else-if="currentAgentConfig?.id === 'thinker'" />
                  <User v-else />
                </el-icon>
                <!-- 说话动态脉冲波 -->
                <span
                  v-if="isPlaying && (isAudioPlaying || audioEnabled)"
                  class="absolute -inset-1 rounded-xl border animate-ping pointer-events-none opacity-30"
                  :style="{ borderColor: currentAgentConfig?.color || '#3B82F6' }"
                ></span>
              </div>
              <div>
                <div class="flex items-center gap-1.5">
                  <span class="text-xs sm:text-sm font-bold text-[var(--text-primary)]">
                    {{ currentAgentConfig?.name || '导师' }}
                  </span>
                  <span
                    class="text-[10px] px-1.5 py-0.2 rounded-full font-medium"
                    :style="{
                      backgroundColor: currentAgentConfig?.color ? `${currentAgentConfig.color}15` : 'rgba(59, 130, 246, 0.12)',
                      color: currentAgentConfig?.color || '#3B82F6'
                    }"
                  >
                    {{ currentAgentConfig?.role || '角色发言' }}
                  </span>
                </div>
                <div class="text-[10px] text-[var(--text-muted)] flex items-center gap-1 mt-0.5">
                  <span>动作 {{ currentActionIndex + 1 }}/{{ totalActionsInScene }}</span>
                  <span v-if="isPlaying && (isAudioPlaying || audioEnabled)" class="flex items-center gap-0.5 ml-1">
                    <span class="w-0.5 h-1.5 bg-[var(--color-success)] rounded-full animate-pulse"></span>
                    <span class="w-0.5 h-2.5 bg-[var(--color-success)] rounded-full animate-pulse" style="animation-delay: 150ms"></span>
                    <span class="w-0.5 h-1 bg-[var(--color-success)] rounded-full animate-pulse" style="animation-delay: 300ms"></span>
                  </span>
                </div>
              </div>
            </div>

            <!-- 台词正文 -->
            <div class="flex-1 min-w-0 px-2">
              <p class="text-xs sm:text-sm text-[var(--text-primary)] font-normal leading-relaxed line-clamp-2">
                {{ currentAction?.text || '（微课剧本正在就位...）' }}
              </p>
            </div>

            <!-- 步进操作 -->
            <div class="flex items-center gap-1.5 flex-shrink-0">
              <button
                @click="prevActionOrScene"
                :disabled="currentSceneIndex === 0 && currentActionIndex === 0"
                title="上一句/上一幕"
                class="w-8 h-8 rounded-lg bg-[var(--bg-primary)] hover:bg-[var(--bg-hover)] border border-[var(--border-default)] disabled:opacity-30 text-[var(--text-primary)] flex items-center justify-center transition-colors text-xs cursor-pointer"
              >
                <el-icon><ArrowLeft /></el-icon>
              </button>
              <button
                @click="nextActionOrScene"
                :disabled="currentSceneIndex === totalScenes - 1 && currentActionIndex === totalActionsInScene - 1"
                title="下一句/下一幕"
                class="w-8 h-8 rounded-lg bg-[var(--bg-primary)] hover:bg-[var(--bg-hover)] border border-[var(--border-default)] disabled:opacity-30 text-[var(--text-primary)] flex items-center justify-center transition-colors text-xs cursor-pointer"
              >
                <el-icon><ArrowRight /></el-icon>
              </button>
            </div>
          </div>

          <!-- 下层：统一核心播放控制与进度岛 -->
          <div class="w-full px-4 py-2 rounded-xl bg-[var(--surface-card)] border border-[var(--border-default)] flex items-center justify-between gap-4 shadow-xs">
            <!-- 上一幕 -->
            <button
              @click="prevScene"
              :disabled="currentSceneIndex === 0"
              title="上一幕"
              class="px-3 py-1.5 rounded-lg text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] disabled:opacity-30 disabled:hover:bg-transparent transition-colors flex items-center gap-1.5 cursor-pointer"
            >
              <el-icon><ArrowLeft /></el-icon>
              <span class="hidden sm:inline">上一幕</span>
            </button>

            <!-- 核心播放/暂停控制与幕进度指示器 -->
            <div class="flex items-center gap-3.5">
              <button
                @click="togglePlay"
                class="px-6 py-2 rounded-full font-semibold text-xs sm:text-sm flex items-center gap-2 shadow-sm transition-all cursor-pointer"
                :class="isPlaying
                  ? 'bg-[var(--bg-secondary)] text-[var(--text-primary)] border border-[var(--border-default)] hover:bg-[var(--bg-hover)]'
                  : 'bg-[var(--color-primary)] text-[var(--text-inverse)] hover:opacity-90 shadow-sm'"
              >
                <el-icon class="text-base"><VideoPause v-if="isPlaying" /><VideoPlay v-else /></el-icon>
                <span>{{ isPlaying ? '暂停' : '播放' }}</span>
              </button>

              <!-- 幕切换胶囊指示器 -->
              <div class="hidden sm:flex items-center gap-1.5 pl-2 border-l border-[var(--border-default)]">
                <button
                  v-for="(_, sIdx) in totalScenes"
                  :key="sIdx"
                  @click="jumpToScene(Number(sIdx))"
                  :title="`跳转到第 ${Number(sIdx) + 1} 幕`"
                  class="h-2 rounded-full transition-all duration-200 cursor-pointer"
                  :class="[
                    Number(sIdx) === currentSceneIndex
                      ? 'w-5 bg-[var(--color-primary)]'
                      : (Number(sIdx) < currentSceneIndex ? 'w-2 bg-[var(--color-success)] opacity-80 hover:opacity-100' : 'w-2 bg-[var(--border-default)] hover:bg-[var(--border-hover)]')
                  ]"
                ></button>
              </div>
            </div>

            <!-- 下一幕 -->
            <button
              @click="nextScene"
              :disabled="currentSceneIndex === totalScenes - 1"
              title="下一幕"
              class="px-3 py-1.5 rounded-lg text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] disabled:opacity-30 disabled:hover:bg-transparent transition-colors flex items-center gap-1.5 cursor-pointer"
            >
              <span class="hidden sm:inline">下一幕</span>
              <el-icon><ArrowRight /></el-icon>
            </button>
          </div>
        </div>
      </main>

      <!-- 侧边栏：微课幕次目录 (Slide-over Drawer) -->
      <aside
        v-show="showSidebar"
        class="absolute inset-y-0 right-0 w-72 sm:w-80 bg-[var(--surface-card)]/98 backdrop-blur-xl border-l border-[var(--border-default)] z-30 flex flex-col shadow-xl transition-all duration-300"
      >
        <div class="p-4 border-b border-[var(--border-default)] flex items-center justify-between">
          <div class="flex items-center gap-2">
            <el-icon class="text-[var(--color-primary)]"><Tickets /></el-icon>
            <h3 class="text-sm font-semibold text-[var(--text-primary)]">课堂幕次目录</h3>
          </div>
          <el-button circle size="small" @click="showSidebar = false">
            <el-icon><Fold /></el-icon>
          </el-button>
        </div>

        <div class="flex-1 overflow-y-auto p-3 space-y-2">
          <div
            v-for="(sc, sIdx) in classroomData.scenes"
            :key="sc.id || sIdx"
            @click="jumpToScene(Number(sIdx))"
            class="p-3 rounded-xl border transition-all cursor-pointer group"
            :class="[
              Number(sIdx) === currentSceneIndex
                ? 'bg-[var(--color-primary-light)] border-[var(--color-primary)] text-[var(--color-primary)] shadow-xs font-medium'
                : 'border-[var(--border-default)] hover:border-[var(--border-hover)] bg-[var(--bg-primary)] text-[var(--text-primary)]'
            ]"
          >
            <div class="flex items-start justify-between gap-2">
              <span class="text-[11px] font-bold px-1.5 py-0.5 rounded bg-[var(--bg-secondary)]">
                #{{ Number(sIdx) + 1 }}
              </span>
              <span
                class="text-[10px] px-2 py-0.5 rounded-full font-medium"
                :class="sc.type === 'quiz' ? 'bg-[var(--color-warning)]/15 text-[var(--color-warning)]' : 'bg-[var(--color-primary)]/15 text-[var(--color-primary)]'"
              >
                {{ sc.type === 'quiz' ? '随堂测验' : '讲解幕' }}
              </span>
            </div>
            <h4 class="text-xs font-semibold mt-1.5 line-clamp-1 group-hover:opacity-80">
              {{ sc.title }}
            </h4>
            <div class="flex items-center justify-between text-[10px] text-[var(--text-muted)] mt-2">
              <span>{{ (sc.actions || []).length }} 条剧本动作</span>
              <span v-if="Number(sIdx) < currentSceneIndex" class="text-[var(--color-success)] font-medium">已完成</span>
              <span v-else-if="Number(sIdx) === currentSceneIndex" class="text-[var(--color-primary)] font-bold">演播中</span>
            </div>
          </div>
        </div>

        <!-- 引用源文档 -->
        <div v-if="sourceDocuments.length > 0" class="p-3 border-t border-[var(--border-default)] bg-[var(--bg-secondary)]/50 flex-shrink-0">
          <div class="flex items-center gap-1.5 mb-2 text-xs font-semibold text-[var(--text-muted)]">
            <el-icon class="w-3.5 h-3.5 text-[var(--color-primary)]"><Tickets /></el-icon>
            <span>本课引用参考材料 ({{ sourceDocuments.length }})</span>
          </div>
          <div class="space-y-1.5 max-h-36 overflow-y-auto">
            <div
              v-for="doc in sourceDocuments"
              :key="doc.id"
              class="text-xs p-2 rounded-lg bg-[var(--surface-card)] border border-[var(--border-default)] flex items-center justify-between gap-2"
              :title="doc.filename"
            >
              <span class="truncate flex-1 font-medium text-[var(--text-primary)]">{{ doc.filename }}</span>
              <span v-if="doc.file_size" class="text-[10px] text-[var(--text-muted)] flex-shrink-0">
                {{ formatSize(doc.file_size) }}
              </span>
            </div>
          </div>
        </div>
      </aside>
    </div>

    <!-- 研讨历史全量抽屉 -->
    <el-drawer
      v-model="showHistoryDrawer"
      title="本节课堂研讨完整记录"
      direction="rtl"
      size="380px"
    >
      <div class="space-y-3 p-1">
        <div
          v-for="(act, aIdx) in currentScene?.actions || []"
          :key="act.id || aIdx"
          class="p-3 rounded-xl border border-[var(--border-default)] bg-[var(--bg-primary)]"
        >
          <div class="flex items-center gap-2 mb-1.5">
            <span class="text-xs font-bold" :style="{ color: getAgentConfig(act.agentId)?.color || 'var(--color-primary)' }">
              {{ getAgentConfig(act.agentId)?.name || '角色' }}
            </span>
            <span class="text-[10px] text-[var(--text-muted)]">
              {{ getAgentConfig(act.agentId)?.role }}
            </span>
          </div>
          <p class="text-xs text-[var(--text-primary)] leading-relaxed">
            {{ act.text }}
          </p>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useClassroomStore } from '../stores/classroom'
import api from '../services/api'
import {
  ArrowLeft,
  ArrowRight,
  VideoPlay,
  VideoPause,
  Reading,
  Promotion,
  Fold,
  List,
  Loading,
  CircleCheckFilled,
  CircleCloseFilled,
  Tickets,
  GraduationCap,
  Brain,
  User,
  ChatLineRound,
} from '../components/icons'

const route = useRoute()
const router = useRouter()
const classroomStore = useClassroomStore()

const classroomId = computed(() => (route.params.id as string) || '')
const playerContainer = ref<HTMLElement | null>(null)

const loading = ref(true)
const error = ref('')
const classroomData = ref<any>(null)

// 播放控制状态
const currentSceneIndex = ref(0)
const currentActionIndex = ref(0)
const isPlaying = ref(false)
const audioEnabled = ref(true)
const autoAdvance = ref(true)
const showSidebar = ref(false)
const showHistoryDrawer = ref(false)

// 播放倍速
const playbackRates = [0.75, 1.0, 1.25, 1.5]
const playbackRate = ref(1.0)

function cyclePlaybackRate() {
  const currentIdx = playbackRates.indexOf(playbackRate.value)
  const nextIdx = (currentIdx + 1) % playbackRates.length
  playbackRate.value = playbackRates[nextIdx]
  if (currentAudio) {
    currentAudio.playbackRate = playbackRate.value
  }
}

// 测验场景专用状态
const selectedOption = ref('')
const quizSubmitted = ref(false)

// 定时器与语音合成
let actionTimer: any = null
let currentAudio: HTMLAudioElement | null = null
let currentAudioUrl: string | null = null
const isAudioPlaying = ref(false)

// 计算属性
const courseTitle = computed(() => classroomData.value?.stage?.name || 'AI 互动微课')
const totalScenes = computed(() => (classroomData.value?.scenes || []).length)
const currentScene = computed(() => classroomData.value?.scenes?.[currentSceneIndex.value] || null)
const sourceDocuments = computed(() => {
  return (
    classroomData.value?.sourceDocuments ||
    classroomData.value?.stage?.sourceDocuments ||
    []
  )
})

function formatSize(bytes?: number): string {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
const canvasTheme = computed(() => currentScene.value?.content?.canvas?.theme || {})
const canvasElements = computed(() => currentScene.value?.content?.canvas?.elements || [])
const currentActions = computed(() => currentScene.value?.actions || [])
const totalActionsInScene = computed(() => currentActions.value.length)
const currentAction = computed(() => currentActions.value[currentActionIndex.value] || null)

const agentConfigs = computed(() => classroomData.value?.stage?.generatedAgentConfigs || [
  { id: 'teacher', name: '苏老师', role: '主讲导师', color: '#3B82F6' },
  { id: 'curious', name: '求知同学', role: '探索学员', color: '#F59E0B' },
  { id: 'thinker', name: '学霸', role: '深度思考者', color: '#10B981' },
])

const currentAgentConfig = computed(() => {
  const agId = currentAction.value?.agentId
  return agentConfigs.value.find((a: any) => a.id === agId) || agentConfigs.value[0]
})

function getAgentConfig(agentId: string) {
  return agentConfigs.value.find((a: any) => a.id === agentId)
}

// 测验场景相关
const currentQuiz = computed(() => {
  if (currentScene.value?.type !== 'quiz') return null
  return currentScene.value?.quiz || currentScene.value?.content?.quiz || null
})

const currentQuizOptions = computed(() => {
  return currentQuiz.value?.options || ['选项 A', '选项 B', '选项 C', '选项 D']
})

const isCurrentAnswerCorrect = computed(() => {
  if (!currentQuiz.value || !selectedOption.value) return false
  const ans = (currentQuiz.value.answer || '').trim()
  return selectedOption.value.trim() === ans || selectedOption.value.startsWith(ans)
})

function getOptionLetter(idx: number | string): string {
  return String.fromCharCode(65 + Number(idx))
}

function selectQuizOption(opt: string) {
  if (quizSubmitted.value) return
  selectedOption.value = opt
  quizSubmitted.value = true
}

function isOptionCorrect(opt: string): boolean {
  const ans = (currentQuiz.value?.answer || '').trim()
  return opt.trim() === ans || opt.startsWith(ans)
}

function getQuizOptionClass(opt: string): string {
  if (!quizSubmitted.value) {
    return 'bg-[var(--surface-card)] hover:bg-[var(--bg-hover)] border-[var(--border-default)] text-[var(--text-primary)]'
  }
  if (isOptionCorrect(opt)) {
    return 'bg-[var(--color-success-light)] border-[var(--color-success)] text-[var(--color-success)] font-medium'
  }
  if (selectedOption.value === opt) {
    return 'bg-[var(--color-error-light)] border-[var(--color-error)] text-[var(--color-error)] font-medium'
  }
  return 'bg-[var(--bg-secondary)] border-[var(--border-default)] opacity-60 text-[var(--text-muted)]'
}

function getQuizOptionBadgeClass(opt: string): string {
  if (!quizSubmitted.value) {
    return 'bg-[var(--bg-secondary)] text-[var(--text-primary)] border border-[var(--border-default)]'
  }
  if (isOptionCorrect(opt)) {
    return 'bg-[var(--color-success)] text-[var(--text-inverse)]'
  }
  if (selectedOption.value === opt) {
    return 'bg-[var(--color-error)] text-[var(--text-inverse)]'
  }
  return 'bg-[var(--bg-tertiary)] text-[var(--text-muted)]'
}

// 16:9 画布坐标换算（基准 1000 x 562.5）
function getElementStyle(el: any) {
  const leftPct = (el.left / 1000) * 100
  const topPct = (el.top / 562.5) * 100
  const widthPct = (el.width / 1000) * 100
  const heightPct = (el.height / 562.5) * 100

  return {
    left: `${leftPct}%`,
    top: `${topPct}%`,
    width: `${widthPct}%`,
    height: `${heightPct}%`,
  }
}

function isElementHighlighted(elementId: string): boolean {
  if (!currentAction.value) return false
  return (
    currentAction.value.targetElementId === elementId ||
    currentAction.value.spotlight === elementId
  )
}

// 播放生命周期与台词推进
function togglePlay() {
  isPlaying.value = !isPlaying.value
  if (isPlaying.value) {
    playCurrentAction()
  } else {
    stopCurrentPlayback()
  }
}

function cleanupAudio() {
  if (currentAudio) {
    currentAudio.pause()
    currentAudio.onended = null
    currentAudio.onerror = null
    currentAudio = null
  }
  if (currentAudioUrl) {
    URL.revokeObjectURL(currentAudioUrl)
    currentAudioUrl = null
  }
  isAudioPlaying.value = false
}

function stopCurrentPlayback() {
  if (actionTimer) {
    clearTimeout(actionTimer)
    actionTimer = null
  }
  cleanupAudio()
  if ('speechSynthesis' in window) {
    try {
      window.speechSynthesis.cancel()
    } catch {
      // ignore
    }
  }
}

function toggleAudio() {
  audioEnabled.value = !audioEnabled.value
  if (!audioEnabled.value) {
    stopCurrentPlayback()
  } else if (audioEnabled.value && isPlaying.value) {
    playCurrentAction()
  }
}

async function playCurrentAction() {
  stopCurrentPlayback()
  if (!isPlaying.value) return

  const act = currentAction.value
  if (!act) {
    nextScene()
    return
  }

  // 若静音或无台词，走按字长自动切幕
  if (!audioEnabled.value || !act.text) {
    scheduleFallbackTimer(act.text || '')
    return
  }

  const voiceName = act.voice || currentAgentConfig.value?.voice || ''

  // 1. 优先尝试调用后端高质量 TTS 接口 (/api/tts/generate)
  try {
    const resp = await api.post('/tts/generate', {
      text: act.text,
      voice: voiceName,
      speed: playbackRate.value,
    }, {
      responseType: 'blob',
      timeout: 7000,
    })

    if (!isPlaying.value) return

    if (resp.data && resp.data.size > 0) {
      cleanupAudio()
      currentAudioUrl = URL.createObjectURL(resp.data)
      currentAudio = new Audio(currentAudioUrl)
      currentAudio.playbackRate = playbackRate.value

      currentAudio.onplay = () => {
        isAudioPlaying.value = true
      }
      currentAudio.onended = () => {
        cleanupAudio()
        if (isPlaying.value && autoAdvance.value) {
          actionTimer = setTimeout(() => {
            nextActionOrScene()
          }, 600)
        }
      }
      currentAudio.onerror = () => {
        cleanupAudio()
        playWithWebSpeechFallback(act.text)
      }

      await currentAudio.play()
      return
    }
  } catch {
    // 后端 TTS 未配置或在单测/无网络环境下，平滑降级至 Web Speech API
  }

  // 2. 降级为 Web Speech API
  playWithWebSpeechFallback(act.text)
}

function playWithWebSpeechFallback(text: string) {
  if (audioEnabled.value && 'speechSynthesis' in window && text) {
    try {
      const utter = new SpeechSynthesisUtterance(text)
      utter.lang = 'zh-CN'
      utter.rate = playbackRate.value
      utter.onstart = () => {
        isAudioPlaying.value = true
      }
      utter.onend = () => {
        isAudioPlaying.value = false
        if (isPlaying.value && autoAdvance.value) {
          actionTimer = setTimeout(() => {
            nextActionOrScene()
          }, 800)
        }
      }
      utter.onerror = () => {
        isAudioPlaying.value = false
        scheduleFallbackTimer(text)
      }
      window.speechSynthesis.speak(utter)
      return
    } catch {
      // 语音异常回退至计时器
    }
  }

  scheduleFallbackTimer(text)
}

function scheduleFallbackTimer(text: string) {
  const duration = Math.max(2500, Math.min(12000, (text.length * 150) / playbackRate.value))
  actionTimer = setTimeout(() => {
    if (isPlaying.value && autoAdvance.value) {
      nextActionOrScene()
    }
  }, duration)
}

function nextActionOrScene() {
  if (currentActionIndex.value < totalActionsInScene.value - 1) {
    currentActionIndex.value++
    if (isPlaying.value) playCurrentAction()
  } else {
    nextScene()
  }
}

function prevActionOrScene() {
  if (currentActionIndex.value > 0) {
    currentActionIndex.value--
    if (isPlaying.value) playCurrentAction()
  } else if (currentSceneIndex.value > 0) {
    currentSceneIndex.value--
    currentActionIndex.value = 0
    resetSceneState()
    if (isPlaying.value) playCurrentAction()
  }
}

function nextScene() {
  if (currentSceneIndex.value < totalScenes.value - 1) {
    currentSceneIndex.value++
    currentActionIndex.value = 0
    resetSceneState()
    if (isPlaying.value) playCurrentAction()
  } else {
    isPlaying.value = false
    stopCurrentPlayback()
  }
}

function prevScene() {
  if (currentSceneIndex.value > 0) {
    currentSceneIndex.value--
    currentActionIndex.value = 0
    resetSceneState()
    if (isPlaying.value) playCurrentAction()
  }
}

function jumpToScene(idx: number | string) {
  currentSceneIndex.value = Number(idx)
  currentActionIndex.value = 0
  resetSceneState()
  if (isPlaying.value) playCurrentAction()
}

function resetSceneState() {
  selectedOption.value = ''
  quizSubmitted.value = false
  stopCurrentPlayback()
}

// 全屏切换
function toggleFullscreen() {
  if (!playerContainer.value) return
  if (!document.fullscreenElement) {
    playerContainer.value.requestFullscreen().catch(() => {})
  } else {
    document.exitFullscreen().catch(() => {})
  }
}

function goBack() {
  stopCurrentPlayback()
  if (classroomId.value) {
    router.push(`/courses/${classroomId.value}`)
  } else {
    router.push('/courses')
  }
}

// 键盘快捷键支持
function handleKeyDown(e: KeyboardEvent) {
  if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
  if (e.code === 'Space') {
    e.preventDefault()
    togglePlay()
  } else if (e.code === 'ArrowRight') {
    e.preventDefault()
    nextActionOrScene()
  } else if (e.code === 'ArrowLeft') {
    e.preventDefault()
    prevActionOrScene()
  } else if (e.key === 'm' || e.key === 'M') {
    toggleAudio()
  } else if (e.key === 'f' || e.key === 'F') {
    toggleFullscreen()
  }
}

async function loadData() {
  loading.value = true
  error.value = ''
  try {
    const data = await classroomStore.fetchClassroomDetail(classroomId.value)
    if (!data) {
      error.value = '未检索到课堂课件数据'
      return
    }
    classroomData.value = data
    currentSceneIndex.value = 0
    currentActionIndex.value = 0
    resetSceneState()
  } catch (err: any) {
    error.value = err?.response?.data?.detail || err.message || '加载微课失败'
  } finally {
    loading.value = false
  }
}

watch(
  () => route.params.id,
  (newId) => {
    if (newId) loadData()
  }
)

onMounted(() => {
  loadData()
  window.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  stopCurrentPlayback()
  window.removeEventListener('keydown', handleKeyDown)
})
</script>

<style scoped>
.aspect-video {
  aspect-ratio: 16 / 9;
}
</style>
