import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// 打包产物输出到插件静态目录 views/status/（AstrBot 页面服务直接服务该目录）
export default defineConfig({
  plugins: [vue()],
  base: './',
  build: {
    outDir: resolve(__dirname, '../views/status'),
    emptyOutDir: false,
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      output: {
        entryFileNames: 'assets/[name]-[hash].js',
        chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash][extname]'
      }
    }
  }
})
