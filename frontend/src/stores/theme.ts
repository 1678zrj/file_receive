/**
 * 主题（浅色 / 深色）
 *
 * 实现要点：
 *  1. 只维护一个 `mode`，实际视觉效果全部由 `html.dark` 上的 CSS 变量切换完成
 *     （见 `styles/main.css` 的 `:root` 与 `html.dark` 两套令牌）。
 *  2. 首帧防闪白：`index.html` 里有一段内联脚本会在 Vue 挂载前就打好 `html.dark`，
 *     这里 init() 只是把同一份偏好读进 store，保证按钮图标状态与页面一致。
 *  3. Element Plus 的深色变量（`element-plus/theme-chalk/dark/css-vars.css`）也是挂在
 *     `html.dark` 下的，所以加上这个类之后组件库会自动跟随。
 */
import { defineStore } from 'pinia'

export type ThemeMode = 'light' | 'dark'

/** 与 index.html 内联脚本里的键名必须一致 */
export const THEME_KEY = 'cc_theme'

function readStored(): ThemeMode | null {
  try {
    const v = localStorage.getItem(THEME_KEY)
    return v === 'dark' || v === 'light' ? v : null
  } catch {
    return null
  }
}

function systemPrefersDark(): boolean {
  try {
    return typeof window !== 'undefined' && !!window.matchMedia
      ? window.matchMedia('(prefers-color-scheme: dark)').matches
      : false
  } catch {
    return false
  }
}

/** 把模式写到 <html> 上（CSS 变量与 Element Plus 深色变量都靠这个类生效） */
function applyTheme(mode: ThemeMode) {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  root.classList.toggle('dark', mode === 'dark')
  // 让原生滚动条 / 表单控件 / 自动填充跟随
  root.style.colorScheme = mode
}

export const useThemeStore = defineStore('theme', {
  state: () => ({
    /** 当前模式；init() 之前先用系统偏好兜底，保证第一次渲染就是对的 */
    mode: (readStored() ?? (systemPrefersDark() ? 'dark' : 'light')) as ThemeMode,
    /** 用户是否显式选择过（选择过就不再跟随系统变化） */
    explicit: readStored() !== null,
  }),
  getters: {
    isDark: (s) => s.mode === 'dark',
  },
  actions: {
    /** 启动时调用：与 index.html 内联脚本的结果对齐（内联脚本可能已按系统偏好加过类） */
    init() {
      const stored = readStored()
      if (stored) {
        this.mode = stored
        this.explicit = true
      } else {
        this.mode = systemPrefersDark() ? 'dark' : 'light'
        this.explicit = false
      }
      applyTheme(this.mode)
      // 没显式选过时跟随系统切换
      if (typeof window !== 'undefined' && window.matchMedia) {
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
          if (this.explicit) return
          this.mode = e.matches ? 'dark' : 'light'
          applyTheme(this.mode)
        })
      }
    },

    set(mode: ThemeMode) {
      this.mode = mode
      this.explicit = true
      try {
        localStorage.setItem(THEME_KEY, mode)
      } catch {
        /* 隐私模式下写不了也不影响本次会话 */
      }
      applyTheme(mode)
    },

    toggle() {
      this.set(this.mode === 'dark' ? 'light' : 'dark')
    },
  },
})
