<template>
  <div class="auth-page min-h-screen relative overflow-hidden flex items-center justify-center p-6">
    <!-- ── 全屏品牌背景层 ── -->
    <div class="bg-base"></div>
    <div class="bg-grid"></div>
    <div class="bg-glow bg-glow-1"></div>
    <div class="bg-glow bg-glow-2"></div>
    <div class="bg-ring bg-ring-1"></div>
    <div class="bg-ring bg-ring-2"></div>
    <div
      v-for="(p, i) in particles"
      :key="i"
      class="bg-particle"
      :style="{
        left: p.left + '%',
        width: p.size + 'px',
        height: p.size + 'px',
        animationDelay: p.delay + 's',
        animationDuration: p.duration + 's'
      }"
    ></div>

    <!-- ── 中央悬浮卡片 ── -->
    <div class="relative z-10 w-full max-w-md">
      <!-- 品牌标识 -->
      <div class="text-center mb-8">
        <CopilotBotAvatar ref="botLogo" :size="80" mood="idle" class="mx-auto mb-5 block" />
        <h1 class="text-2xl font-semibold text-white tracking-tight">注册 Study Copilot</h1>
        <p class="text-white/70 mt-2 text-sm">创建账户，开启智能学习之旅</p>
      </div>

      <!-- 注册卡片 -->
      <form @submit.prevent="handleRegister">
        <div class="card-shell rounded-2xl">
          <el-card ref="registerCard" :body-style="{ padding: '32px' }" shadow="never">
            <div class="space-y-4">
              <div>
                <label for="register-username" class="block text-sm text-[var(--text-secondary)] mb-1">用户名</label>
                <el-input
                  id="register-username"
                  v-model="form.username"
                  placeholder="请输入用户名"
                  required
                />
              </div>

              <div>
                <label for="register-email" class="block text-sm text-[var(--text-secondary)] mb-1">邮箱</label>
                <el-input
                  id="register-email"
                  v-model="form.email"
                  type="email"
                  placeholder="请输入邮箱"
                  required
                />
              </div>

              <div>
                <label for="register-password" class="block text-sm text-[var(--text-secondary)] mb-1">密码</label>
                <el-input
                  id="register-password"
                  v-model="form.password"
                  type="password"
                  show-password
                  placeholder="请输入密码"
                  required
                />
              </div>

              <el-button
                type="primary"
                class="login-btn w-full !h-11 text-[15px] font-medium"
                :disabled="loading"
                native-type="submit"
              >
                {{ loading ? '注册中...' : '注册' }}
              </el-button>

              <p v-if="error" class="text-sm text-[var(--color-error)] text-center">{{ error }}</p>
            </div>
          </el-card>
        </div>
      </form>

      <p class="text-center mt-6 text-sm text-white/70">
        已有账户?
        <router-link to="/login" class="text-white font-medium hover:underline">
          立即登录
        </router-link>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import CopilotBotAvatar from '@/components/CopilotBotAvatar.vue'
import gsap from 'gsap'
import { useAuthStore } from '../stores/auth'
import { useRouter } from 'vue-router'
import type { AxiosError } from 'axios'
import { useReducedMotion } from '../composables/useReducedMotion'

const authStore = useAuthStore()
const router = useRouter()
const { prefersReduced } = useReducedMotion()

const registerCard = ref<HTMLElement | null>(null)
const botLogo = ref<InstanceType<typeof CopilotBotAvatar> | null>(null)
let ctx: gsap.Context | null = null

const form = ref({
  username: '',
  email: '',
  password: ''
})
const loading = ref(false)
const error = ref('')

const particles = [
  { left: 10, size: 3, delay: 0, duration: 18 },
  { left: 22, size: 2, delay: 3, duration: 22 },
  { left: 35, size: 4, delay: 7, duration: 16 },
  { left: 48, size: 2, delay: 1, duration: 24 },
  { left: 62, size: 3, delay: 5, duration: 19 },
  { left: 75, size: 2, delay: 9, duration: 21 },
  { left: 88, size: 3, delay: 2, duration: 17 }
]

async function handleRegister(): Promise<void> {
  loading.value = true
  error.value = ''

  try {
    await authStore.register(form.value.username, form.value.email, form.value.password)
    router.push('/login')
  } catch (e) {
    const axiosError = e as AxiosError<{ detail: string }>
    error.value = axiosError.response?.data?.detail || '注册失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (prefersReduced.value) return
  ctx = gsap.context(() => {
    if (registerCard.value) {
      gsap.from(registerCard.value, {
        y: 34,
        opacity: 0,
        duration: 0.65,
        ease: 'power2.out'
      })
    }
    nextTick(() => botLogo.value?.play?.('acknowledge'))
  })
})

onUnmounted(() => {
  ctx?.revert()
})
</script>

<style scoped>
/* ── 全屏品牌背景层（黑白单色系：纯黑画布） ── */
.bg-base {
  position: absolute;
  inset: 0;
  background: #000000;
}
.bg-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.05) 1px, transparent 1px);
  background-size: 38px 38px;
  -webkit-mask-image: radial-gradient(ellipse at 50% 42%, black, transparent 72%);
  mask-image: radial-gradient(ellipse at 50% 42%, black, transparent 72%);
}
.bg-glow {
  position: absolute;
  border-radius: 9999px;
  filter: blur(80px);
  opacity: 0.45;
  will-change: transform;
}
.bg-glow-1 {
  width: 440px;
  height: 440px;
  background: #3f3f44;
  top: -120px;
  left: -100px;
  animation: glow-drift-1 26s ease-in-out infinite;
}
.bg-glow-2 {
  width: 400px;
  height: 400px;
  background: #5a5a5f;
  bottom: -140px;
  right: -80px;
  animation: glow-drift-2 32s ease-in-out infinite;
}
.bg-ring {
  position: absolute;
  border-radius: 9999px;
  border: 1px solid rgba(255, 255, 255, 0.09);
}
.bg-ring-1 {
  width: 520px;
  height: 520px;
  top: 50%;
  left: 50%;
  animation: ring-spin 120s linear infinite;
}
.bg-ring-2 {
  width: 680px;
  height: 680px;
  top: 50%;
  left: 50%;
  animation: ring-spin-rev 160s linear infinite;
}

/* ── 背景粒子 ── */
.bg-particle {
  position: absolute;
  bottom: -12px;
  border-radius: 9999px;
  background: rgba(255, 255, 255, 0.55);
  opacity: 0;
  animation: rise linear infinite;
  will-change: transform, opacity;
}

/* ── 悬浮卡片外壳 ── */
.card-shell {
  position: relative;
  padding: 1px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.28), rgba(255, 255, 255, 0.1));
  border-radius: 18px;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.55), 0 6px 18px rgba(0, 0, 0, 0.4);
}
.card-shell :deep(.el-card) {
  border-radius: 17px;
  border: none;
}

/* ── 注册按钮 ── */
.login-btn {
  transition: transform 0.18s ease, box-shadow 0.18s ease, filter 0.18s ease;
}
.login-btn:hover {
  transform: translateY(-1px);
  filter: brightness(1.06);
  box-shadow: 0 6px 16px rgba(255, 255, 255, 0.25);
}
.login-btn:active {
  transform: translateY(0);
}

/* ── 动画 Keyframes ── */
@keyframes glow-drift-1 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(-56px, 42px) scale(1.12); }
}
@keyframes glow-drift-2 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(48px, -52px) scale(1.14); }
}
@keyframes ring-spin {
  from { transform: translate(-50%, -50%) rotate(0deg); }
  to { transform: translate(-50%, -50%) rotate(360deg); }
}
@keyframes ring-spin-rev {
  from { transform: translate(-50%, -50%) rotate(0deg); }
  to { transform: translate(-50%, -50%) rotate(-360deg); }
}
@keyframes rise {
  0% { transform: translateY(0); opacity: 0; }
  12% { opacity: 0.55; }
  82% { opacity: 0.35; }
  100% { transform: translateY(-105vh); opacity: 0; }
}

@media (prefers-reduced-motion: reduce) {
  .bg-glow-1,
  .bg-glow-2,
  .bg-ring-1,
  .bg-ring-2,
  .bg-particle {
    animation: none;
  }
  .bg-particle {
    opacity: 0;
  }
}
</style>