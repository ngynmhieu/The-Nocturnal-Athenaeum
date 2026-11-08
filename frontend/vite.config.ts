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
    // Pinned to match the Docker frontend's published port (docker-compose.yml)
    // and supabase/config.toml's site_url/additional_redirect_urls — Supabase
    // only trusts redirects back to :3000, so dev and container must agree.
    port: 3000,
    // Fail loudly if :3000 is taken (e.g. the Docker frontend is still up)
    // instead of silently falling back to another port and reintroducing
    // this exact mismatch.
    strictPort: true,
    // Listen on every network interface, not just localhost, so a phone on the
    // same Wi-Fi can open http://<this-machine's-LAN-IP>:3000. The backend stays
    // private on localhost: the browser only ever talks to this server, which
    // forwards API calls through the proxy below.
    host: true,
    proxy: {
      // Local Supabase (Docker, :54321), reached through this same origin so a
      // phone on the LAN never needs "localhost" — see shared/config/env.ts.
      // Listed before the backend's '/auth' so '/auth/v1' matches here first.
      ...Object.fromEntries(
        ['/auth/v1', '/rest/v1', '/storage/v1', '/realtime/v1'].map((prefix) => [
          prefix,
          { target: process.env.SUPABASE_PROXY_TARGET ?? 'http://localhost:54321', changeOrigin: true, ws: true },
        ])
      ),
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
      '/models': {
        target: `http://${process.env.BACKEND_HOST ?? 'localhost'}:${process.env.BACKEND_PORT ?? '8000'}`,
        changeOrigin: true,
      },
      '/conversations': {
        target: `http://${process.env.BACKEND_HOST ?? 'localhost'}:${process.env.BACKEND_PORT ?? '8000'}`,
        changeOrigin: true,
      },
      '/auth': {
        target: `http://${process.env.BACKEND_HOST ?? 'localhost'}:${process.env.BACKEND_PORT ?? '8000'}`,
        changeOrigin: true,
      },
      '/read': {
        target: `http://${process.env.BACKEND_HOST ?? 'localhost'}:${process.env.BACKEND_PORT ?? '8000'}`,
        changeOrigin: true,
      },
    },
  },
})
