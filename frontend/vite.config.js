import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 前端 dev server：默认 5173
// 后端已配置 CORS（allow 本机 5173），故 axios 直接请求 http://127.0.0.1:8000/api/v1
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    host: true,
  },
  build: {
    rollupOptions: {
      output: {
        // 拆分第三方大依赖，优化首屏加载
        manualChunks: {
          vue: ['vue', 'vue-router', 'pinia'],
          'element-plus': ['element-plus', '@element-plus/icons-vue'],
          axios: ['axios'],
        },
      },
    },
  },
})
