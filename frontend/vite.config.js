import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
// Docker 里前端容器访问后端要用服务名 backend,本地直跑用 localhost:8000
const apiTarget = process.env.VITE_API_TARGET || 'http://localhost:8000'
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': apiTarget } },
  build: {
    rollupOptions: {
      // ECharts 整包 ~1MB,单独切块后首屏只加载 React,报告页再按需拉图表
      output: { manualChunks: { echarts: ['echarts', 'echarts-for-react'], react: ['react', 'react-dom'] } },
    },
    chunkSizeWarningLimit: 1200,
  },
})
