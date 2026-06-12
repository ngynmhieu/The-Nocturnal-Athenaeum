import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      // Backend serves prefix-less routes (/chat, /health). List each here
      // so the dev server forwards them instead of serving the SPA shell.
      '/chat': {
        target: `http://${process.env.BACKEND_HOST ?? 'localhost'}:${process.env.BACKEND_PORT ?? '8000'}`,
        changeOrigin: true,
      },
      '/health': {
        target: `http://${process.env.BACKEND_HOST ?? 'localhost'}:${process.env.BACKEND_PORT ?? '8000'}`,
        changeOrigin: true,
      },
    },
  },
})
