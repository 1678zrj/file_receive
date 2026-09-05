/** 路由配置 + 全局守卫 */
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { title: '登录', public: true },
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    children: [
      { path: '', redirect: '/dashboard' },
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('@/views/DashboardView.vue'),
        meta: { title: '仪表盘' },
      },
      {
        path: 'courses',
        name: 'courses',
        component: () => import('@/views/CourseCenterView.vue'),
        meta: { title: '课程广场' },
      },
      {
        path: 'my-courses',
        name: 'my-courses',
        component: () => import('@/views/MyCoursesView.vue'),
        meta: { title: '我的课程' },
      },
      {
        path: 'courses/:id',
        name: 'course-detail',
        component: () => import('@/views/CourseDetailView.vue'),
        meta: { title: '课程详情' },
      },
      {
        path: 'knowledge',
        name: 'knowledge',
        component: () => import('@/views/KnowledgeView.vue'),
        meta: { title: '知识库管理' },
      },
      {
        path: 'qa',
        name: 'qa',
        component: () => import('@/views/QaView.vue'),
        meta: { title: 'AI 问答' },
      },
      {
        path: 'profile',
        name: 'profile',
        component: () => import('@/views/ProfileView.vue'),
        meta: { title: '个人中心' },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
    meta: { title: '页面不存在', public: true },
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  // 首次导航前先恢复会话
  if (!auth.ready) await auth.restore()

  if (!to.meta.public && !auth.isLoggedIn) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  // 已登录访问登录页则回首页
  if (to.name === 'login' && auth.isLoggedIn) {
    return { path: '/' }
  }
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} · 云课堂` : '云课堂 · 在线教学平台'
})
