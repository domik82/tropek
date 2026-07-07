import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    environment: 'happy-dom',
    setupFiles: ['./src/test-setup.ts'],
    globals: true,
    exclude: ['**/node_modules/**', '**/.claude/**'],
    pool: 'forks',
    deps: {
      optimizer: {
        web: {
          include: [
            'echarts',
            'echarts-for-react',
            'lucide-react',
            'react-day-picker',
            'cmdk',
            'zod',
          ],
        },
      },
    },
  },
  server: {
    watch: {
      // Native inotify by default. Polling across the whole tree (esp. node_modules)
      // is a known WSL2 CPU-pegger, so it's opt-in only — set VITE_USE_POLLING=1 if
      // HMR misses edits (e.g. saving from a Windows-side editor over the \\wsl$ mount).
      usePolling: process.env.VITE_USE_POLLING === '1',
      interval: 1000,
      // Never watch these — even under polling they're the main source of CPU load.
      ignored: ['**/node_modules/**', '**/dist/**', '**/.git/**', '**/coverage/**'],
    },
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL ?? 'http://localhost:9080',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
