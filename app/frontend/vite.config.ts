import path from "path"
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 80,
    strictPort: true,
    allowedHosts: ['gateway', 'localhost'],
    hmr: {
      clientPort: 80,
    },
    proxy: {
      '/api': {
        target: 'http://gateway:80',
        changeOrigin: true,
      },
      '/storage': {
        target: 'http://gateway:80',
        changeOrigin: true,
      },
      '/media': {
        target: 'http://gateway:80',
        changeOrigin: true,
      }
    },
    watch: {
      usePolling: true,
    },
  },
})
