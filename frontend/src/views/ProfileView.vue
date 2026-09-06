<template>
  <div class="max-w-4xl mx-auto px-6 py-10">
    <!-- ── 顶部个人名片 ── -->
    <div class="card p-6 md:p-8 mb-8 relative overflow-hidden">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-6 relative z-10">
        <div class="flex items-center gap-5">
          <!-- 头像展示与切换：支持自定义上传、首字母渐变与 Copilot 伴侣机器人 -->
          <div class="relative group cursor-pointer" @click="triggerAvatarUpload" title="点击更换头像">
            <img
              v-if="userPrefs.avatarType === 'custom' && userPrefs.customAvatar"
              :src="userPrefs.customAvatar"
              alt="用户头像"
              class="w-16 h-16 rounded-2xl object-cover border-2 border-[var(--border-default)] shadow-md transition-transform group-hover:scale-105"
            />
            <div
              v-else-if="userPrefs.avatarType === 'letter'"
              class="w-16 h-16 rounded-2xl bg-gradient-to-br from-[var(--color-brand-from)] to-[var(--color-brand-to)]
                     flex items-center justify-center text-2xl font-semibold text-[var(--text-inverse)] shadow-md transition-transform group-hover:scale-105"
            >
              {{ avatarLetter }}
            </div>
            <div
              v-else
              class="w-16 h-16 rounded-2xl bg-[var(--bg-secondary)] border border-[var(--border-default)]
                     flex items-center justify-center shadow-md transition-transform group-hover:scale-105"
            >
              <CopilotBotAvatar :size="52" mood="idle" :gaze="userPrefs.botGaze" />
            </div>
            <span class="absolute -bottom-1 -right-1 w-5 h-5 rounded-full bg-[var(--surface-card)] border border-[var(--border-default)] flex items-center justify-center text-[10px] text-[var(--text-muted)] shadow-sm group-hover:text-[var(--text-primary)]">
              <el-icon><Edit /></el-icon>
            </span>
            <!-- 隐藏的图片文件上传 input -->
            <input
              ref="avatarInputRef"
              type="file"
              accept="image/png,image/jpeg,image/webp,image/gif"
              class="hidden"
              @change="handleAvatarFileChange"
            />
          </div>

          <div class="min-w-0">
            <div class="flex items-center gap-2.5 flex-wrap">
              <h1 class="text-2xl font-bold text-[var(--text-primary)] truncate">{{ authStore.user?.username || '学习者' }}</h1>
              <span class="text-xs px-2.5 py-0.5 rounded-full bg-[var(--color-primary-light)] text-[var(--color-primary)] font-medium">
                本地知识库
              </span>
            </div>
            <p class="text-sm text-[var(--text-secondary)] mt-1.5 line-clamp-1 italic">
              "{{ userPrefs.bio }}"
            </p>
            <div class="flex items-center gap-4 mt-2 text-xs text-[var(--text-muted)] flex-wrap">
              <span>{{ authStore.user?.email }}</span>
              <span>•</span>
              <span>陪伴学习第 <strong class="text-[var(--text-primary)]">{{ memberDays }}</strong> 天</span>
              <span>•</span>
              <span>加入于 {{ memberSince }}</span>
            </div>
          </div>
        </div>

        <div class="flex sm:flex-col items-center sm:items-end gap-2">
          <el-button size="small" @click="activeTab = 'profile'">
            <el-icon class="mr-1"><Edit /></el-icon>编辑资料
          </el-button>
          <el-button size="small" type="danger" text @click="handleLogout">
            退出登录
          </el-button>
        </div>
      </div>
    </div>

    <!-- ── 学习资产数据看板 ── -->
    <div class="grid grid-cols-2 sm:grid-cols-5 gap-3.5 mb-8">
      <router-link
        to="/documents"
        class="card p-4 hover:border-[var(--color-primary)] transition-all group flex flex-col justify-between"
      >
        <div class="flex items-center justify-between text-[var(--text-muted)] group-hover:text-[var(--text-primary)]">
          <span class="text-xs font-medium">知识文档</span>
          <el-icon class="w-4 h-4"><Document /></el-icon>
        </div>
        <div class="mt-3">
          <div class="text-2xl font-bold text-[var(--text-primary)] tabular-nums">{{ documentStore.documents.length }}</div>
          <div class="text-[11px] text-[var(--text-muted)] mt-0.5 truncate">{{ totalDocSize }}</div>
        </div>
      </router-link>

      <router-link
        to="/courses"
        class="card p-4 hover:border-[var(--color-primary)] transition-all group flex flex-col justify-between"
      >
        <div class="flex items-center justify-between text-[var(--text-muted)] group-hover:text-[var(--text-primary)]">
          <span class="text-xs font-medium">课程空间</span>
          <el-icon class="w-4 h-4"><Reading /></el-icon>
        </div>
        <div class="mt-3">
          <div class="text-2xl font-bold text-[var(--text-primary)] tabular-nums">{{ courseStore.courses.length }}</div>
          <div class="text-[11px] text-[var(--text-muted)] mt-0.5">多模块归档</div>
        </div>
      </router-link>

      <router-link
        to="/notes"
        class="card p-4 hover:border-[var(--color-primary)] transition-all group flex flex-col justify-between"
      >
        <div class="flex items-center justify-between text-[var(--text-muted)] group-hover:text-[var(--text-primary)]">
          <span class="text-xs font-medium">学习笔记</span>
          <el-icon class="w-4 h-4"><EditPen /></el-icon>
        </div>
        <div class="mt-3">
          <div class="text-2xl font-bold text-[var(--text-primary)] tabular-nums">{{ noteStore.notes.length }}</div>
          <div class="text-[11px] text-[var(--text-muted)] mt-0.5">语义索引</div>
        </div>
      </router-link>

      <router-link
        to="/chat"
        class="card p-4 hover:border-[var(--color-primary)] transition-all group flex flex-col justify-between"
      >
        <div class="flex items-center justify-between text-[var(--text-muted)] group-hover:text-[var(--text-primary)]">
          <span class="text-xs font-medium">AI 问答</span>
          <el-icon class="w-4 h-4"><ChatDotSquare /></el-icon>
        </div>
        <div class="mt-3">
          <div class="text-2xl font-bold text-[var(--text-primary)] tabular-nums">{{ chatStore.sessions.length }}</div>
          <div class="text-[11px] text-[var(--text-muted)] mt-0.5">会话历史</div>
        </div>
      </router-link>

      <router-link
        to="/analysis"
        class="card p-4 hover:border-[var(--color-primary)] transition-all group flex flex-col justify-between col-span-2 sm:col-span-1"
      >
        <div class="flex items-center justify-between text-[var(--text-muted)] group-hover:text-[var(--text-primary)]">
          <span class="text-xs font-medium">练习巩固</span>
          <el-icon class="w-4 h-4"><TrendCharts /></el-icon>
        </div>
        <div class="mt-3">
          <div class="text-2xl font-bold text-[var(--text-primary)] tabular-nums">{{ quizStore.knowledgeStats.total_quizzes }} 题</div>
          <div class="text-[11px] text-[var(--color-success)] mt-0.5 font-medium">
            正确率 {{ quizStore.knowledgeStats.accuracy_rate }}%
          </div>
        </div>
      </router-link>
    </div>

    <!-- ── 标签分类设置卡片 ── -->
    <div class="card p-6 md:p-8">
      <el-tabs v-model="activeTab" class="profile-tabs">
        <!-- ── TAB 1: 个人资料与偏好 ── -->
        <el-tab-pane label="个人资料" name="profile">
          <div class="py-2 space-y-6 max-w-2xl">
            <div>
              <h2 class="text-base font-semibold text-[var(--text-primary)]">基本信息</h2>
              <p class="text-xs text-[var(--text-muted)] mt-0.5">修改用于登录和展示的账户信息</p>
            </div>

            <form class="space-y-5" @submit.prevent="handleSaveProfile">
              <div>
                <label class="block text-sm text-[var(--text-secondary)] mb-2 font-medium">头像定制与风格</label>
                <div class="flex items-center gap-3 flex-wrap">
                  <el-radio-group v-model="userPrefs.avatarType" @change="saveUserPrefs">
                    <el-radio-button label="letter">首字母渐变</el-radio-button>
                    <el-radio-button label="bot">伴侣机器人</el-radio-button>
                    <el-radio-button label="custom" :disabled="!userPrefs.customAvatar">自定义照片</el-radio-button>
                  </el-radio-group>
                  <el-button size="small" @click="triggerAvatarUpload">
                    <el-icon class="mr-1"><Edit /></el-icon>上传图片头像
                  </el-button>
                  <el-button v-if="userPrefs.customAvatar" size="small" text type="danger" @click="clearCustomAvatar">
                    清除照片
                  </el-button>
                </div>
                <p class="text-xs text-[var(--text-muted)] mt-1.5">支持 PNG、JPG、WebP，本地自动裁剪与压缩</p>
              </div>

              <div>
                <label for="profile-username" class="block text-sm text-[var(--text-secondary)] mb-1.5 font-medium">用户名</label>
                <el-input
                  id="profile-username"
                  v-model="profileForm.username"
                  placeholder="请输入用户名"
                  :disabled="profileSaving"
                />
              </div>

              <div>
                <label for="profile-email" class="block text-sm text-[var(--text-secondary)] mb-1.5 font-medium">邮箱地址</label>
                <el-input
                  id="profile-email"
                  v-model="profileForm.email"
                  type="email"
                  placeholder="请输入邮箱"
                  :disabled="profileSaving"
                />
              </div>

              <div>
                <label for="profile-bio" class="block text-sm text-[var(--text-secondary)] mb-1.5 font-medium">学习宣言 / 个性签名</label>
                <el-input
                  id="profile-bio"
                  v-model="userPrefs.bio"
                  type="textarea"
                  :rows="2"
                  placeholder="写一句激励自己的话..."
                  maxlength="80"
                  show-word-limit
                />
              </div>

              <div class="pt-4 border-t border-[var(--border-default)]">
                <h3 class="text-sm font-semibold text-[var(--text-primary)] mb-1">学习与做题习惯</h3>
                <p class="text-xs text-[var(--text-muted)] mb-4">设置生成练习题时的默认配置</p>

                <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label class="block text-xs text-[var(--text-secondary)] mb-1">默认选择题数</label>
                    <el-input-number v-model="userPrefs.defaultChoiceCount" :min="1" :max="10" class="!w-full" />
                  </div>
                  <div>
                    <label class="block text-xs text-[var(--text-secondary)] mb-1">默认简答题数</label>
                    <el-input-number v-model="userPrefs.defaultShortCount" :min="1" :max="5" class="!w-full" />
                  </div>
                </div>
              </div>

              <div class="pt-4 border-t border-[var(--border-default)]">
                <h3 class="text-sm font-semibold text-[var(--text-primary)] mb-1">AI 助手交互风格</h3>
                <p class="text-xs text-[var(--text-muted)] mb-3">调整 RAG 对话在回答时的语言风格偏好</p>
                <el-radio-group v-model="userPrefs.aiStyle">
                  <el-radio-button label="rigorous">学术严谨</el-radio-button>
                  <el-radio-button label="balanced">平衡适中</el-radio-button>
                  <el-radio-button label="concise">凝练要点</el-radio-button>
                </el-radio-group>
              </div>

              <p v-if="profileError" class="text-sm text-[var(--color-error)]">{{ profileError }}</p>
              <p v-if="profileSaved" class="text-sm text-[var(--color-success)]">个人资料已更新</p>

              <div class="flex justify-end pt-2">
                <el-button type="primary" native-type="submit" :loading="profileSaving">
                  保存资料与偏好
                </el-button>
              </div>
            </form>
          </div>
        </el-tab-pane>

        <!-- ── TAB 2: 外观与伴侣定制 ── -->
        <el-tab-pane label="界面与伴侣" name="appearance">
          <div class="py-2 space-y-8 max-w-2xl">
            <!-- 主题外观选择卡片 -->
            <div>
              <h2 class="text-base font-semibold text-[var(--text-primary)]">主题外观</h2>
              <p class="text-xs text-[var(--text-muted)] mt-0.5 mb-4">选择符合你习惯的视觉界面模式</p>

              <div class="grid grid-cols-3 gap-3.5">
                <!-- 亮色 -->
                <div
                  class="card p-3 cursor-pointer border-2 transition-all text-center flex flex-col items-center gap-2"
                  :class="themeStore.theme === 'light' ? 'border-[var(--color-primary)] ring-1 ring-[var(--color-primary)]' : 'border-[var(--border-default)] hover:border-[var(--border-hover)]'"
                  @click="themeStore.setTheme('light')"
                >
                  <div class="w-full h-12 rounded-lg bg-[#f0f0fa] border border-[#e0e0e8] flex items-center justify-center shadow-inner">
                    <span class="w-4 h-4 rounded-full bg-[#000000]"></span>
                  </div>
                  <div class="flex items-center gap-1.5 text-xs font-medium text-[var(--text-primary)]">
                    <el-icon><Sunny /></el-icon> 亮色模式
                  </div>
                </div>

                <!-- 暗色 -->
                <div
                  class="card p-3 cursor-pointer border-2 transition-all text-center flex flex-col items-center gap-2"
                  :class="themeStore.theme === 'dark' ? 'border-[var(--color-primary)] ring-1 ring-[var(--color-primary)]' : 'border-[var(--border-default)] hover:border-[var(--border-hover)]'"
                  @click="themeStore.setTheme('dark')"
                >
                  <div class="w-full h-12 rounded-lg bg-[#000000] border border-[#3a3a3f] flex items-center justify-center shadow-inner">
                    <span class="w-4 h-4 rounded-full bg-[#ffffff]"></span>
                  </div>
                  <div class="flex items-center gap-1.5 text-xs font-medium text-[var(--text-primary)]">
                    <el-icon><Moon /></el-icon> 暗色模式
                  </div>
                </div>

                <!-- 跟随系统 -->
                <div
                  class="card p-3 cursor-pointer border-2 transition-all text-center flex flex-col items-center gap-2"
                  :class="themeStore.theme === 'system' ? 'border-[var(--color-primary)] ring-1 ring-[var(--color-primary)]' : 'border-[var(--border-default)] hover:border-[var(--border-hover)]'"
                  @click="themeStore.setTheme('system')"
                >
                  <div class="w-full h-12 rounded-lg bg-gradient-to-r from-[#f0f0fa] to-[#000000] border border-[var(--border-default)] flex items-center justify-center shadow-inner">
                    <el-icon class="text-[var(--text-primary)]"><Setting /></el-icon>
                  </div>
                  <div class="flex items-center gap-1.5 text-xs font-medium text-[var(--text-primary)]">
                    跟随系统
                  </div>
                </div>
              </div>
            </div>

            <!-- Copilot 伴侣定制 -->
            <div class="pt-6 border-t border-[var(--border-default)]">
              <h2 class="text-base font-semibold text-[var(--text-primary)]">Copilot 伴侣机器人</h2>
              <p class="text-xs text-[var(--text-muted)] mt-0.5 mb-4">定制桌面端陪伴 AI 的实时物理反馈</p>

              <div class="space-y-4">
                <div class="flex items-center justify-between p-3.5 bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-default)]">
                  <div>
                    <div class="text-sm font-medium text-[var(--text-primary)]">视线注视跟踪 (Gaze Tracking)</div>
                    <div class="text-xs text-[var(--text-muted)] mt-0.5">机器人的瞳孔将跟随您的鼠标指针位置灵动注视</div>
                  </div>
                  <el-switch v-model="userPrefs.botGaze" @change="saveUserPrefs" />
                </div>

                <div class="flex items-center justify-between p-3.5 bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-default)]">
                  <div>
                    <div class="text-sm font-medium text-[var(--text-primary)]">空闲打瞌睡动画 (Sleep Cycle)</div>
                    <div class="text-xs text-[var(--text-muted)] mt-0.5">长时间无操作时，机器人将自动进入打瞌睡或蛋形呼吸微动画</div>
                  </div>
                  <el-switch v-model="userPrefs.botIdleSleep" @change="saveUserPrefs" />
                </div>
              </div>
            </div>

            <!-- 动效与无障碍 -->
            <div class="pt-6 border-t border-[var(--border-default)]">
              <h2 class="text-base font-semibold text-[var(--text-primary)]">无障碍与动效偏好</h2>
              <div class="mt-3 p-3.5 bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-default)] flex items-center justify-between">
                <div>
                  <div class="text-sm font-medium text-[var(--text-primary)]">系统动效减弱 (prefers-reduced-motion)</div>
                  <div class="text-xs text-[var(--text-muted)] mt-0.5">
                    当前状态：{{ prefersReduced ? '已开启（自动降级过度动画为瞬时响应）' : '未开启（正常启用 GSAP 物理动效）' }}
                  </div>
                </div>
                <span class="text-xs px-2.5 py-1 rounded-full font-medium" :class="prefersReduced ? 'bg-[var(--color-warning-light)] text-[var(--color-warning)]' : 'bg-[var(--color-success-light)] text-[var(--color-success)]'">
                  {{ prefersReduced ? 'Reduced' : 'Standard' }}
                </span>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <!-- ── TAB 3: 安全与凭证 ── -->
        <el-tab-pane label="安全与密码" name="security">
          <div class="py-2 space-y-6 max-w-2xl">
            <div>
              <h2 class="text-base font-semibold text-[var(--text-primary)]">修改登录密码</h2>
              <p class="text-xs text-[var(--text-muted)] mt-0.5">请定期更新您的访问凭证，确保学习数据安全</p>
            </div>

            <form class="space-y-4" @submit.prevent="handleChangePassword">
              <div>
                <label for="profile-old-password" class="block text-sm text-[var(--text-secondary)] mb-1.5 font-medium">原密码</label>
                <el-input
                  id="profile-old-password"
                  v-model="passwordForm.oldPassword"
                  type="password"
                  show-password
                  placeholder="请输入当前使用的密码"
                  :disabled="passwordSaving"
                  required
                />
              </div>

              <div>
                <label for="profile-new-password" class="block text-sm text-[var(--text-secondary)] mb-1.5 font-medium">新密码</label>
                <el-input
                  id="profile-new-password"
                  v-model="passwordForm.newPassword"
                  type="password"
                  show-password
                  placeholder="请输入新密码（至少 6 位）"
                  :disabled="passwordSaving"
                  required
                />
                <!-- 密码强度指示器 -->
                <div v-if="passwordForm.newPassword" class="mt-2 space-y-1">
                  <div class="flex items-center justify-between text-xs">
                    <span class="text-[var(--text-muted)]">密码强度</span>
                    <span :class="passwordStrength.colorClass" class="font-medium">{{ passwordStrength.text }}</span>
                  </div>
                  <div class="h-1.5 w-full bg-[var(--bg-tertiary)] rounded-full overflow-hidden">
                    <div
                      class="h-full transition-all duration-300 rounded-full"
                      :class="passwordStrength.barClass"
                      :style="{ width: `${passwordStrength.score}%` }"
                    ></div>
                  </div>
                </div>
              </div>

              <div>
                <label for="profile-confirm-password" class="block text-sm text-[var(--text-secondary)] mb-1.5 font-medium">确认新密码</label>
                <el-input
                  id="profile-confirm-password"
                  v-model="passwordForm.confirmPassword"
                  type="password"
                  show-password
                  placeholder="请再次输入新密码"
                  :disabled="passwordSaving"
                  required
                />
              </div>

              <p v-if="passwordError" class="text-sm text-[var(--color-error)]">{{ passwordError }}</p>
              <p v-if="passwordChanged" class="text-sm text-[var(--color-success)]">密码已成功更新</p>

              <div class="flex justify-end pt-2">
                <el-button type="primary" native-type="submit" :loading="passwordSaving">
                  更新密码
                </el-button>
              </div>
            </form>

            <div class="pt-6 border-t border-[var(--border-default)]">
              <h3 class="text-sm font-semibold text-[var(--text-primary)] mb-1">会话与凭证安全</h3>
              <p class="text-xs text-[var(--text-muted)] mb-3 leading-relaxed">
                Study Copilot 采用双 Token（Access + Refresh）自动静默刷新保护。若在非受信任设备上使用，请在学习结束后及时退出。
              </p>
            </div>
          </div>
        </el-tab-pane>

        <!-- ── TAB 4: 存储与系统信息 ── -->
        <el-tab-pane label="存储与系统" name="system">
          <div class="py-2 space-y-6 max-w-2xl">
            <div>
              <h2 class="text-base font-semibold text-[var(--text-primary)]">知识库与存储占用</h2>
              <p class="text-xs text-[var(--text-muted)] mt-0.5 mb-4">本地向量知识库存储概况</p>

              <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div class="p-4 bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-default)]">
                  <span class="text-xs text-[var(--text-muted)]">文档累计占用</span>
                  <div class="text-xl font-bold text-[var(--text-primary)] mt-1">{{ totalDocSize }}</div>
                  <span class="text-[11px] text-[var(--text-muted)] mt-0.5 block">共 {{ documentStore.documents.length }} 份资料</span>
                </div>

                <div class="p-4 bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-default)]">
                  <span class="text-xs text-[var(--text-muted)]">向量检索切片</span>
                  <div class="text-xl font-bold text-[var(--text-primary)] mt-1">{{ totalChunks }} Chunks</div>
                  <span class="text-[11px] text-[var(--text-muted)] mt-0.5 block">FAISS + pgvector 混合索引</span>
                </div>
              </div>
            </div>

            <!-- AI 引擎配置提示 -->
            <div class="pt-6 border-t border-[var(--border-default)]">
              <div class="flex items-center justify-between mb-3">
                <div>
                  <h3 class="text-sm font-semibold text-[var(--text-primary)]">当前 AI 引擎与模型配置</h3>
                  <p class="text-xs text-[var(--text-muted)] mt-0.5">本地多模型抽象与接口状态</p>
                </div>
                <router-link to="/model-config">
                  <el-button size="small">
                    <el-icon class="mr-1"><Setting /></el-icon>模型设置
                  </el-button>
                </router-link>
              </div>

              <div class="space-y-2 text-xs p-3.5 bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-default)]">
                <div class="flex justify-between py-1 border-b border-[var(--border-default)]">
                  <span class="text-[var(--text-muted)]">LLM 模型：</span>
                  <span class="font-medium text-[var(--text-primary)]">{{ llmModelName }}</span>
                </div>
                <div class="flex justify-between py-1 border-b border-[var(--border-default)]">
                  <span class="text-[var(--text-muted)]">Embedding 向量模型：</span>
                  <span class="font-medium text-[var(--text-primary)] truncate max-w-[280px]">{{ embeddingModelName }}</span>
                </div>
                <div class="flex justify-between py-1">
                  <span class="text-[var(--text-muted)]">消息协议：</span>
                  <span class="font-medium text-[var(--text-primary)] uppercase">{{ messageFormat }} API</span>
                </div>
              </div>
            </div>

            <!-- 维护操作 -->
            <div class="pt-6 border-t border-[var(--border-default)]">
              <h3 class="text-sm font-semibold text-[var(--text-primary)] mb-1">系统维护与清理</h3>
              <p class="text-xs text-[var(--text-muted)] mb-3">清理临时草稿与本地会话缓存</p>

              <div class="flex items-center gap-3">
                <el-button size="small" @click="clearLocalDrafts">
                  清理本地草稿缓存
                </el-button>
                <router-link to="/tasks">
                  <el-button size="small">
                    查看后台任务队列
                  </el-button>
                </router-link>
              </div>
            </div>

            <!-- 系统信息 -->
            <div class="pt-6 border-t border-[var(--border-default)] text-xs text-[var(--text-muted)] flex items-center justify-between">
              <span>Study Copilot v2.0 (Agentic RAG)</span>
              <span>FastAPI + Vue3 + pgvector</span>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useDocumentStore } from '../stores/document'
import { useCourseStore } from '../stores/course'
import { useNoteStore } from '../stores/note'
import { useChatStore } from '../stores/chat'
import { useQuizStore } from '../stores/quiz'
import { useThemeStore } from '../stores/theme'
import { useConfigStore } from '../stores/config'
import { useToastStore } from '../stores/toast'
import { useReducedMotion } from '../composables/useReducedMotion'
import { formatSize } from '../composables/useFormat'
import CopilotBotAvatar from '@/components/CopilotBotAvatar.vue'
import { useUserPrefs } from '@/composables/useUserPrefs'
import {
  Document, Reading, EditPen, ChatDotSquare, TrendCharts,
  Sunny, Moon, Edit, Setting
} from '@/components/icons'
import type { AxiosError } from 'axios'

const authStore = useAuthStore()
const documentStore = useDocumentStore()
const courseStore = useCourseStore()
const noteStore = useNoteStore()
const chatStore = useChatStore()
const quizStore = useQuizStore()
const themeStore = useThemeStore()
const configStore = useConfigStore()
const toast = useToastStore()
const router = useRouter()
const { prefersReduced } = useReducedMotion()
const { prefs: userPrefs, savePreferences, setCustomAvatar, removeCustomAvatar } = useUserPrefs()

const activeTab = ref('profile')

const llmModelName = computed(() => chatStore.config.modelName || '默认推理模型')
const embeddingModelName = ref('shibing624/text2vec-base-chinese (768维)')
const messageFormat = computed(() => chatStore.config.messageFormat || 'openai')

// ── 头像上传与控制 ──
const avatarInputRef = ref<HTMLInputElement | null>(null)

function triggerAvatarUpload(): void {
  avatarInputRef.value?.click()
}

function clearCustomAvatar(): void {
  removeCustomAvatar()
  toast.info('已清除自定义头像')
}

function handleAvatarFileChange(e: Event): void {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  if (!file.type.startsWith('image/')) {
    toast.error('请选择有效的图片文件')
    return
  }

  // 使用 FileReader + Canvas 客户端压缩到 128x128
  const reader = new FileReader()
  reader.onload = (loadEvent) => {
    const img = new Image()
    img.onload = () => {
      const canvas = document.createElement('canvas')
      const size = 128
      canvas.width = size
      canvas.height = size
      const ctx = canvas.getContext('2d')
      if (!ctx) return

      // 居中按较短边正方形裁剪
      const minSide = Math.min(img.width, img.height)
      const sx = (img.width - minSide) / 2
      const sy = (img.height - minSide) / 2
      ctx.drawImage(img, sx, sy, minSide, minSide, 0, 0, size, size)

      const base64 = canvas.toDataURL('image/webp', 0.85)
      setCustomAvatar(base64)
      toast.success('头像更换成功')
    }
    img.src = loadEvent.target?.result as string
  }
  reader.readAsDataURL(file)
  // 清空选择框以便重复选择相同文件
  target.value = ''
}

function saveUserPrefs(): void {
  savePreferences()
}

// ── 资料表单 ──
const profileForm = ref({
  username: '',
  email: ''
})
const profileSaving = ref(false)
const profileError = ref('')
const profileSaved = ref(false)

// ── 密码表单 ──
const passwordForm = ref({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})
const passwordSaving = ref(false)
const passwordError = ref('')
const passwordChanged = ref(false)

/** 密码强度动态计算 */
const passwordStrength = computed(() => {
  const pwd = passwordForm.value.newPassword
  if (!pwd) return { score: 0, text: '无', barClass: 'bg-transparent', colorClass: 'text-[var(--text-muted)]' }

  let score = 0
  if (pwd.length >= 6) score += 25
  if (pwd.length >= 10) score += 25
  if (/[0-9]/.test(pwd)) score += 20
  if (/[a-zA-Z]/.test(pwd)) score += 15
  if (/[^a-zA-Z0-9]/.test(pwd)) score += 15

  if (score < 40) {
    return { score, text: '弱', barClass: 'bg-[var(--color-error)]', colorClass: 'text-[var(--color-error)]' }
  } else if (score < 75) {
    return { score, text: '中等', barClass: 'bg-[var(--color-warning)]', colorClass: 'text-[var(--color-warning)]' }
  }
  return { score: 100, text: '强', barClass: 'bg-[var(--color-success)]', colorClass: 'text-[var(--color-success)]' }
})

/** 头像字母：用户名首字符大写 */
const avatarLetter = computed(() => {
  const name = authStore.user?.username || ''
  return name.trim().charAt(0).toUpperCase() || '?'
})

/** 加入时间与陪伴天数 */
const memberSince = computed(() => {
  const raw = authStore.user?.created_at
  if (!raw) return '未知时间'
  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) return raw
  return date.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })
})

const memberDays = computed(() => {
  const raw = authStore.user?.created_at
  if (!raw) return 1
  const created = new Date(raw).getTime()
  if (Number.isNaN(created)) return 1
  return Math.max(1, Math.floor((Date.now() - created) / (1000 * 60 * 60 * 24)))
})

/** 知识库资产统计 */
const totalDocSize = computed(() => {
  const docs = Array.isArray(documentStore.documents) ? documentStore.documents : []
  const bytes = docs.reduce((acc, d) => acc + (d.file_size || 0), 0)
  return formatSize(bytes)
})

const totalChunks = computed(() => {
  const docs = Array.isArray(documentStore.documents) ? documentStore.documents : []
  return docs.reduce((acc, d) => acc + (d.chunk_count || 0), 0)
})

onMounted(async () => {
  try {
    await Promise.allSettled([
      authStore.fetchUser(),
      documentStore.fetchDocuments(),
      courseStore.fetchCourses(),
      noteStore.fetchNotes(),
      chatStore.fetchSessions(),
      quizStore.fetchKnowledgeStats(),
      configStore.fetchLLMConfig().then(cfg => {
        if (cfg) {
          if (cfg.embedding_model) {
            embeddingModelName.value = `${cfg.embedding_model} (${cfg.embedding_dimension || 768}维)`
          }
          // 单向同步到 chatStore 回显镜像（chatStore.config 是响应式的，llmModelName/messageFormat 均为其 computed）
          if (cfg.model_name) chatStore.config.modelName = cfg.model_name
          if (cfg.provider) chatStore.config.provider = cfg.provider
          if (cfg.message_format) chatStore.config.messageFormat = cfg.message_format
        }
      })
    ])
  } catch {
    // ignore
  }
  profileForm.value.username = authStore.user?.username ?? ''
  profileForm.value.email = authStore.user?.email ?? ''
})

async function handleSaveProfile(): Promise<void> {
  profileSaving.value = true
  profileError.value = ''
  profileSaved.value = false

  try {
    await authStore.updateProfile({
      username: profileForm.value.username,
      email: profileForm.value.email
    })
    saveUserPrefs()
    profileSaved.value = true
    toast.success('资料与偏好已保存')
  } catch (e) {
    const axiosError = e as AxiosError<{ detail: string }>
    profileError.value = axiosError.response?.data?.detail || '保存失败，请稍后再试'
  } finally {
    profileSaving.value = false
  }
}

async function handleChangePassword(): Promise<void> {
  passwordError.value = ''
  passwordChanged.value = false

  if (passwordForm.value.newPassword.length < 6) {
    passwordError.value = '新密码至少需要 6 位'
    return
  }
  if (passwordForm.value.newPassword !== passwordForm.value.confirmPassword) {
    passwordError.value = '两次输入的新密码不一致'
    return
  }

  passwordSaving.value = true
  try {
    await authStore.changePassword(passwordForm.value.oldPassword, passwordForm.value.newPassword)
    passwordChanged.value = true
    passwordForm.value.oldPassword = ''
    passwordForm.value.newPassword = ''
    passwordForm.value.confirmPassword = ''
    toast.success('密码已成功修改')
  } catch (e) {
    const axiosError = e as AxiosError<{ detail: string }>
    passwordError.value = axiosError.response?.data?.detail || '修改失败，请检查原密码'
  } finally {
    passwordSaving.value = false
  }
}

function clearLocalDrafts(): void {
  // 清理草稿相关 localStorage
  for (let i = localStorage.length - 1; i >= 0; i--) {
    const key = localStorage.key(i)
    if (key && (key.startsWith('note_draft_') || key.startsWith('chat_draft_'))) {
      localStorage.removeItem(key)
    }
  }
  toast.success('本地临时草稿已清空')
}

function handleLogout(): void {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.profile-tabs :deep(.el-tabs__item) {
  font-size: 0.925rem;
  font-weight: 500;
  color: var(--text-secondary);
}
.profile-tabs :deep(.el-tabs__item.is-active) {
  color: var(--text-primary);
  font-weight: 600;
}
.profile-tabs :deep(.el-tabs__active-bar) {
  background-color: var(--color-primary);
}
</style>
