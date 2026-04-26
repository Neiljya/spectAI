// vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path' // You might already have this for your @/ aliases

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      // Any request to /api/henrik gets forwarded to HenrikDev automatically
      '/api/henrik': {
        target: 'https://api.henrikdev.xyz',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/henrik/, '')
      }
    }
  }
})