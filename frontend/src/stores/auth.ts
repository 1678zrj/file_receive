/** 鉴权状态管理 */
import { defineStore } from 'pinia'
import { authApi, userApi } from '@/api'
import type { UserCreate, UserInfo, UserLogin } from '@/api/types'
import { UserRole } from '@/api/types'
import { getAccessToken, setAccessToken, registerAuthExpiredHandler } from '@/api/http'

interface AuthState {
  user: UserInfo | null
  /** 是否已完成首次会话恢复（避免路由守卫闪烁） */
  ready: boolean
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    user: null,
    ready: false,
  }),
  getters: {
    isLoggedIn: (s) => !!s.user,
    /** 严格意义上的教师（不含管理员） */
    isTeacher: (s) => !!s.user && s.user.role === UserRole.TEACHER,
    isStudent: (s) => !!s.user && s.user.role === UserRole.STUDENT,
    isAdmin: (s) => !!s.user && s.user.role === UserRole.ADMIN,
    /** 教师或管理员（拥有教学侧权限） */
    isTeacherOrAdmin: (s) => !!s.user && s.user.role >= UserRole.TEACHER,
    /** 判断当前用户是否可「管理」某门课程（该课程教师或全局管理员） */
    canManageCourse: (s) => (teacherId: number | undefined) => {
      if (!s.user) return false
      if (s.user.role === UserRole.ADMIN) return true
      return teacherId != null && s.user.id === teacherId
    },
  },
  actions: {
    async login(payload: UserLogin) {
      const token = await authApi.login(payload)
      setAccessToken(token.access_token)
      this.user = await authApi.me()
    },
    async register(payload: UserCreate) {
      return userApi.register(payload)
    },
    /** 应用启动时尝试用本地 token / refresh cookie 恢复会话 */
    async restore() {
      try {
        if (getAccessToken()) {
          this.user = await authApi.me()
        } else {
          // 尝试用 HttpOnly Cookie 中的 refresh_token 换新 token
          const { access_token } = await authApi.refresh()
          setAccessToken(access_token)
          this.user = await authApi.me()
        }
      } catch {
        this.user = null
        setAccessToken(null)
      } finally {
        this.ready = true
      }
    },
    logout() {
      this.user = null
      setAccessToken(null)
    },
    /** 注册 401 彻底失效时的处理 */
    bindExpiredHandler(goLogin: () => void) {
      registerAuthExpiredHandler(() => {
        this.user = null
        goLogin()
      })
    },
  },
})
