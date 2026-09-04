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
        <h1 class="text-2xl font-semibold text-white tracking-tight">Study Copilot</h1>
        <p class="text-white/70 mt-2 text-sm"><span class="slogan-a">让每一份学习资料</span><span class="slogan-b">都被充分理解</span></p>
      </div>

      <!-- 登录卡片 -->
      <form @submit.prevent="handleLogin">
      <div class="card-shell rounded-2xl">
        <el-card ref="loginCard" :body-style="{ padding: '32px' }" shadow="never">
          <div class="space-y-4">
            <div>
              <label for="login-username" class="block text-sm text-[var(--text-secondary)] mb-1">用户名</label>
              <el-input
                id="login-username"
                v-model="form.username"
                placeholder="请输入用户名"
                required
              />
            </div>

            <div>
              <label for="login-password" class="block text-sm text-[var(--text-secondary)] mb-1">密码</label>
              <el-input
                id="login-password"
                v-model="form.password"
                type="password"
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
              {{ loading ? '登录中...' : '登录' }}
            </el-button>

            <p v-if="error" class="text-sm text-[var(--color-error)] text-center">{{ error }}</p>
          </div>
        </el-card>
      </div>
      </form>

      <p class="text-center mt-6 text-sm text-white/70">
        还没有账户?
        <router-link to="/register" class="text-white font-medium hover:underline">
          立即注册
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
import { useRoute, useRouter } from 'vue-router'
import { useConfigStore } from '../stores/config'
import type { AxiosError } from 'axios'
import { useReducedMotion } from '../composables/useReducedMotion'

const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()
const configStore = useConfigStore()
// P1-1：GSAP 动画降级（prefers-reduced-motion）
const { prefersReduced } = useReducedMotion()

const loginCard = ref<HTMLElement | null>(null)
const botLogo = ref<InstanceType<typeof CopilotBotAvatar> | null>(null)
let ctx: gsap.Context | null = null

const form = ref({
  username: '',
  password: ''
})
const loading = ref(false)
const error = ref('')

// 背景粒子：10 个光点错峰上浮（纯 CSS 动画，reduced-motion 下停用）
const particles = Array.from({ length: 10 }, (_, i) => ({
  left: 5 + ((i * 9.7) % 90),
  size: 3 + (i % 4) * 1.5,
  delay: -(i * 2.4),
  duration: 13 + (i % 5) * 3.5
}))

async function handleLogin(): Promise<void> {
  loading.value = true
  error.value = ''

  try {
    await authStore.login(form.value.username, form.value.password)
    await configStore.syncToChatStore()
    // 回跳到登录前想访问的页面；无记录则回首页（P0-3）
    const redirect = route.query.redirect
    router.push(typeof redirect === 'string' && redirect.startsWith('/') ? redirect : '/')
  } catch (e) {
    const axiosError = e as AxiosError<{ detail: string }>
    error.value = axiosError.response?.data?.detail || '登录失败，请检查用户名和密码'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  // P1-1：减少动态偏好下跳过入场动画
  if (prefersReduced.value) return
  ctx = gsap.context(() => {
    if (loginCard.value) {
      gsap.from(loginCard.value, {
        y: 34,
        opacity: 0,
        duration: 0.65,
        ease: 'power2.out'
      })
    }

    // P8：入场时 bot 点头承认
    nextTick(() => botLogo.value?.play('acknowledge'))

    // slogan 两句依次淡入
    gsap.from('.slogan-a', { opacity: 0, y: 8, duration: 0.5, ease: 'power2.out', delay: 0.28 })
    gsap.from('.slogan-b', { opacity: 0, y: 8, duration: 0.5, ease: 'power2.out', delay: 0.42 })
  })
})

onUnmounted(() => {
  ctx?.revert()
})
</script>

<style scoped>
/* ── 全屏品牌背景层（DESIGN.md 黑白单色系：纯黑画布） ── */
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
  /* 单色系光晕：墨色发光体，替代原品牌蓝 */
  background: #3f3f44;
  top: -120px;
  left: -100px;
  animation: glow-drift-1 26s ease-in-out infinite;
}
.bg-glow-2 {
  width: 400px;
  height: 400px;
  /* 单色系光晕：hairline 灰，替代原紫 */
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

/* ── 背景粒子（缓慢上浮） ── */
.bg-particle {
  position: absolute;
  bottom: -12px;
  border-radius: 9999px;
  background: rgba(255, 255, 255, 0.55);
  opacity: 0;
  animation: rise linear infinite;
  will-change: transform, opacity;
}

/* ── 悬浮卡片外壳（单色系发丝线描边 + 阴影） ── */
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

/* ── 登录按钮 hover 微动 ── */
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

/* ── 减少动态偏好：停用所有装饰动画 ── */
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
