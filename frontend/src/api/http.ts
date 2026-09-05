/**
 * Axios 封装：
 *  - baseURL 走 Vite 代理 (/api -> http://127.0.0.1:8000)
 *  - 请求拦截自动携带 Bearer access_token
 *  - 响应拦截统一提取后端 detail 错误信息
 *  - 401 时通过 HttpOnly Cookie 中的 refresh_token 静默刷新并重放原请求（带并发去重）
 */
import axios, { AxiosError, type AxiosRequestConfig, type InternalAxiosRequestConfig } from 'axios'

export const ACCESS_TOKEN_KEY = 'cc_access_token'

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function setAccessToken(token: string | null) {
  if (token) localStorage.setItem(ACCESS_TOKEN_KEY, token)
  else localStorage.removeItem(ACCESS_TOKEN_KEY)
}

/** 登录失效时的回调（由 auth store 注册，用于清理状态并跳转登录页） */
let onAuthExpired: (() => void) | null = null
export function registerAuthExpiredHandler(fn: () => void) {
  onAuthExpired = fn
}

const http = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  // 携带 refresh_token Cookie（同源代理下有效）
  withCredentials: true,
})

// ------------------------------------------------------------
// 请求拦截：携带 token
// ------------------------------------------------------------
http.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getAccessToken()
  if (token && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ------------------------------------------------------------
// 静默刷新逻辑（并发去重：同一时间只允许一个刷新请求）
// ------------------------------------------------------------
let refreshPromise: Promise<string | null> | null = null

async function silentRefresh(): Promise<string | null> {
  if (refreshPromise) return refreshPromise
  refreshPromise = axios
    .post<{ access_token: string }>(
      '/api/v1/auth/refresh',
      null,
      { withCredentials: true, timeout: 15000 },
    )
    .then((res) => {
      const token = res.data.access_token
      setAccessToken(token)
      return token
    })
    .catch(() => null)
    .finally(() => {
      // 微任务后清空，保证同一事件循环内的 401 共享同一个 promise
      setTimeout(() => (refreshPromise = null), 0)
    })
  return refreshPromise
}

// ------------------------------------------------------------
// 响应拦截：错误提取 + 401 自动刷新重放
// ------------------------------------------------------------
export interface ApiError extends Error {
  status?: number
  detail?: string
}

function extractDetail(err: AxiosError): string {
  const data: any = err.response?.data
  if (data) {
    if (typeof data.detail === 'string') return data.detail
    if (Array.isArray(data.detail)) {
      // FastAPI 422 校验错误格式: detail: [{loc, msg, type}]
      return data.detail.map((d: any) => d.msg || JSON.stringify(d)).join('；')
    }
    if (typeof data === 'string') return data
  }
  if (err.code === 'ECONNABORTED') return '请求超时，请检查网络'
  if (!err.response) return '无法连接服务器，请确认后端已启动'
  return `请求失败 (${err.response.status})`
}

http.interceptors.response.use(
  (res) => res,
  async (err: AxiosError) => {
    const original = err.config as (AxiosRequestConfig & { _retried?: boolean }) | undefined
    const status = err.response?.status

    // 401 且未重试过：尝试静默刷新并重放
    if (status === 401 && original && !original._retried && !original.url?.includes('/auth/refresh') && !original.url?.includes('/auth/login')) {
      original._retried = true
      const token = await silentRefresh()
      if (token) {
        original.headers = { ...original.headers, Authorization: `Bearer ${token}` }
        return http(original)
      }
      // 刷新失败 -> 登录态彻底失效
      setAccessToken(null)
      onAuthExpired?.()
    }

    const apiErr: ApiError = new Error(extractDetail(err))
    apiErr.status = status
    apiErr.detail = extractDetail(err)
    return Promise.reject(apiErr)
  },
)

export default http
