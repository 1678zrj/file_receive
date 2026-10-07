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

/* ------------------------------------------------------------------
 * 兜底：懒加载分包加载失败
 *
 * 所有页面路由都是 `() => import(...)` 的懒加载分包。开发态反复热更新
 * （或部署后旧文件被清理）时，浏览器可能还在按已失效的 chunk 名去请求，
 * `import()` 直接 reject。vue-router 此时只会把错误抛到控制台，**导航静默失败**：
 * 地址栏可能已经变了，但内容区不渲染，用户看到的就是「点菜单没反应／点不进去」。
 *
 * 处理方式：记住用户想去哪 → 整页刷新（刷新会重新拿到最新资源）→ 刷新后继续跳过去。
 * 10 秒内只自动刷新一次，避免资源真的 404 时陷入无限刷新死循环。
 * ------------------------------------------------------------------ */
const CHUNK_RELOAD_AT = 'cc_chunk_reload_at'
const CHUNK_RELOAD_TARGET = 'cc_chunk_reload_target'

/** 是否是「分包/动态导入加载失败」，而不是页面自身的运行时错误 */
function isChunkLoadError(err: unknown): boolean {
  const msg = String((err as Error)?.message ?? err ?? '')
  return /dynamically imported module|Importing a module script failed|Loading chunk|Loading CSS chunk/i.test(msg)
}

/** sessionStorage 在隐私模式等场景可能抛异常，这里全部兜住 */
function safeSession(action: 'get' | 'set' | 'remove', key: string, value?: string) {
  try {
    if (action === 'get') return sessionStorage.getItem(key)
    if (action === 'set') sessionStorage.setItem(key, value ?? '')
    else sessionStorage.removeItem(key)
  } catch {
    /* 忽略：兜底机制本身不该影响正常导航 */
  }
  return null
}

router.onError((err, to) => {
  if (!isChunkLoadError(err)) return
  const last = Number(safeSession('get', CHUNK_RELOAD_AT) || 0)
  if (Date.now() - last < 10_000) return
  safeSession('set', CHUNK_RELOAD_AT, String(Date.now()))
  safeSession('set', CHUNK_RELOAD_TARGET, to.fullPath)
  window.location.reload()
})

/** 上次因分包失效自动刷新时记下的目标路由：刷新后继续把它跳完 */
router.isReady().then(() => {
  const target = safeSession('get', CHUNK_RELOAD_TARGET)
  if (!target) return
  safeSession('remove', CHUNK_RELOAD_TARGET)
  if (target !== router.currentRoute.value.fullPath) router.replace(target).catch(() => {})
})
