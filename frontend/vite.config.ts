import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    host: '127.0.0.1',
    proxy: {
      // 开发环境通过 Vite 代理转发到 FastAPI 后端，避免 CORS
      // 同时保证 refresh_token HttpOnly Cookie 在同源代理下正常工作
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-vue': ['vue', 'vue-router', 'pinia', 'axios'],
          'vendor-ep': ['element-plus', '@element-plus/icons-vue'],
          'vendor-md': ['markdown-it', 'highlight.js'],
        },
      },
    },
  },
})
