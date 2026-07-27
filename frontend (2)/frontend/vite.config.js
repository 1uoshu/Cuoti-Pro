import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src')
    }
  },
  server: {
    port: 5173,
    open: true,
    allowedHosts: true, // 允许 localtunnel 等外部域名访问
    // 代理配置 - 连接后端时修改这里的 target
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true  // 支持 WebSocket 代理
      }
    }
  }
})
