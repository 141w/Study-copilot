<template>
  <div class="relative" data-test="notification-bell-root">
    <el-button
      circle
      size="small"
      aria-label="任务通知"
      data-test="notification-bell"
      @click="toggle"
    >
      <el-icon class="w-5 h-5 relative">
        <Bell />
        <span
          v-if="unread > 0"
          class="nb-badge"
          data-test="notification-badge"
        >
          {{ unread > 99 ? '99+' : unread }}
        </span>
      </el-icon>
    </el-button>

    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0 -translate-y-1"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div v-if="open" class="nb-panel" data-test="notification-panel">
        <div class="nb-panel__head">
          <span class="nb-panel__title">任务通知</span>
          <button
            v-if="unread > 0"
            type="button"
            class="nb-panel__action"
            data-test="notification-read-all"
            @click="onReadAll"
          >
            全部已读
          </button>
        </div>
        <div class="nb-panel__body">
          <div v-if="loading && items.length === 0" class="nb-empty">加载中…</div>
          <div v-else-if="items.length === 0" class="nb-empty">
            暂无通知。后台任务完成后会出现在这里。
          </div>
          <ul v-else class="nb-list">
            <li v-for="n in items" :key="n.id">
              <button
                type="button"
                class="nb-item"
                :class="{ 'nb-item--unread': !n.read }"
                data-test="notification-item"
                @click="onOpen(n)"
              >
                <span class="nb-item__dot" :class="`nb-item__dot--${n.level}`" />
                <span class="nb-item__main">
                  <span class="nb-item__row">
                    <span class="nb-item__title">{{ n.title }}</span>
                    <span class="nb-item__time">{{ fmt(n.completed_at || n.created_at) }}</span>
                  </span>
                  <span class="nb-item__body">{{ n.body }}</span>
                </span>
              </button>
            </li>
          </ul>
        </div>
        <div class="nb-panel__foot">
          <router-link to="/tasks" class="nb-panel__link" @click="open = false">
            查看全部后台任务 →
          </router-link>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Bell } from '@/components/icons'
import { useNotificationStore, type AppNotification } from '@/stores/notification'
import { formatRelativeTime } from '@/composables/useFormat'

const store = useNotificationStore()
const router = useRouter()
const open = ref(false)
let outside: ((e: MouseEvent) => void) | null = null

const unread = computed(() => store.unread)
const items = computed(() => store.items)
const loading = computed(() => store.loading)

function fmt(iso?: string | null): string {
  if (!iso) return ''
  try {
    return formatRelativeTime(iso)
  } catch {
    return ''
  }
}

function toggle(): void {
  open.value = !open.value
  if (open.value) void store.fetchNotifications(false)
}

async function onReadAll(): Promise<void> {
  await store.markAllRead()
}

async function onOpen(n: AppNotification): Promise<void> {
  await store.markRead(n.id)
  open.value = false
  if (n.link) await router.push(n.link)
}

onMounted(() => {
  outside = (e: MouseEvent) => {
    if (!open.value) return
    const root = (e.target as HTMLElement)?.closest?.('[data-test="notification-bell-root"]')
    if (!root) open.value = false
  }
  document.addEventListener('click', outside, true)
})

onBeforeUnmount(() => {
  if (outside) document.removeEventListener('click', outside, true)
})
</script>

<style scoped>
/* 角标挂在 el-icon 上，与圆形按钮中心对齐 */
.nb-badge {
  position: absolute;
  top: -2px;
  right: -4px;
  min-width: 14px;
  height: 14px;
  padding: 0 3px;
  border-radius: 999px;
  background: var(--color-error);
  color: #fff;
  font-size: 9px;
  font-weight: 600;
  line-height: 14px;
  text-align: center;
  pointer-events: none;
  border: 1.5px solid var(--surface-card);
}

.nb-panel {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: min(22rem, calc(100vw - 2rem));
  border-radius: 12px;
  border: 1px solid var(--border-default);
  background: var(--surface-card);
  box-shadow: 0 8px 28px rgb(0 0 0 / 0.1);
  z-index: 50;
  overflow: hidden;
}

.nb-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-default);
}

.nb-panel__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.nb-panel__action {
  border: 0;
  background: transparent;
  font-size: 12px;
  color: var(--color-primary);
  cursor: pointer;
  padding: 0;
}

.nb-panel__action:hover {
  text-decoration: underline;
}

.nb-panel__body {
  max-height: 20rem;
  overflow-y: auto;
}

.nb-empty {
  padding: 1.5rem 1rem;
  text-align: center;
  font-size: 12px;
  color: var(--text-muted);
}

.nb-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.nb-list > li + li {
  border-top: 1px solid var(--border-default);
}

.nb-item {
  width: 100%;
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 10px 12px;
  border: 0;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: background 0.12s ease;
}

.nb-item:hover {
  background: var(--bg-hover);
}

.nb-item--unread {
  background: color-mix(in srgb, var(--color-primary) 4%, transparent);
}

.nb-item__dot {
  margin-top: 5px;
  width: 6px;
  height: 6px;
  border-radius: 999px;
  flex-shrink: 0;
  background: var(--border-default);
}

.nb-item__dot--success { background: var(--color-success); }
.nb-item__dot--error { background: var(--color-error); }
.nb-item__dot--info { background: var(--color-primary); }

.nb-item__main {
  min-width: 0;
  flex: 1;
}

.nb-item__row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: baseline;
}

.nb-item__title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.nb-item__time {
  font-size: 10px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.nb-item__body {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.nb-panel__foot {
  border-top: 1px solid var(--border-default);
  padding: 8px 12px;
}

.nb-panel__link {
  font-size: 12px;
  color: var(--text-secondary);
  text-decoration: none;
}

.nb-panel__link:hover {
  color: var(--text-primary);
}
</style>
