import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
// 代码高亮主题：之前一直没引，导致 hljs-* 的 token 类没有任何颜色，代码块实际是单色的
import 'highlight.js/styles/atom-one-dark.css'
// 数学公式：KaTeX 需要配套 CSS 与字体文件（Vite 会一并处理字体资源）
import 'katex/dist/katex.min.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import { router } from './router'
import { useAuthStore } from './stores/auth'
import '@/styles/main.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(ElementPlus, { locale: zhCn })

// 注册全部 Element Plus 图标为全局组件
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// 登录态彻底失效时（401 刷新失败）跳转登录页
const auth = useAuthStore(pinia)
auth.bindExpiredHandler(() => {
  router.push({ name: 'login', query: { expired: '1' } })
})

app.mount('#app')
