import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '../stores/auth'

declare module 'vue-router' {
  interface RouteMeta {
    /** 该路由是否需要登录态 */
    requiresAuth?: boolean
    /** 是否采用沉浸式全屏布局（隐藏全局顶栏与全局侧边栏） */
    immersive?: boolean
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: () => import('../views/HomeView.vue')
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue')
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('../views/RegisterView.vue')
  },
  {
    path: '/upload',
    name: 'upload',
    component: () => import('../views/UploadView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/chat',
    name: 'chat',
    component: () => import('../views/ChatView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/quiz',
    name: 'quiz',
    component: () => import('../views/QuizView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/analysis',
    name: 'analysis',
    component: () => import('../views/AnalysisView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/model-config',
    name: 'model-config',
    component: () => import('../views/ModelConfigView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/documents',
    name: 'documents',
    component: () => import('../views/DocumentView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/courses',
    name: 'courses',
    component: () => import('../views/CourseListView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/courses/:id',
    name: 'course-detail',
    component: () => import('../views/CourseDetailView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/courses/:id/classroom',
    name: 'course-classroom',
    component: () => import('../views/ClassroomPlayerView.vue'),
    meta: { requiresAuth: true, immersive: true }
  },
  {
    path: '/classroom/:id',
    name: 'classroom-player',
    component: () => import('../views/ClassroomPlayerView.vue'),
    meta: { requiresAuth: true, immersive: true }
  },
  {
    path: '/notes',
    name: 'notes',
    component: () => import('../views/NotesView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/tasks',
    name: 'tasks',
    component: () => import('../views/TasksView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/profile',
    name: 'profile',
    component: () => import('../views/ProfileView.vue'),
    meta: { requiresAuth: true }
  },
  { path: '/:pathMatch(.*)*', redirect: '/' }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, _from, next) => {
  const authStore = useAuthStore()

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    // 记录目标页，登录成功后回跳（P0-3）
    next({ path: '/login', query: { redirect: to.fullPath } })
  } else {
    next()
  }
})

export default router
