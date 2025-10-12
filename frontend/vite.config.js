import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.ico', 'apple-touch-icon.png', 'masked-icon.svg'],
      manifest: {
        name: 'Unicorn Command & Control',
        short_name: 'UC2',
        description: 'Advanced AI Agent Management Platform',
        theme_color: '#ec4899',
        background_color: '#0c0a09',
        display: 'standalone',
        orientation: 'portrait',
        scope: '/',
        start_url: '/',
        icons: [
          {
            src: '/icon-192.png',
            sizes: '192x192',
            type: 'image/png'
          },
          {
            src: '/icon-512.png',
            sizes: '512x512',
            type: 'image/png'
          }
        ]
      }
    })
  ],
  server: {
    port: 8113,
    proxy: {
      '/api': {
        target: 'http://localhost:8112',
        changeOrigin: true,
      },
      '/socket.io': {
        target: 'http://localhost:8112',
        changeOrigin: true,
        ws: true,
      }
    }
  }
})
