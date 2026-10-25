import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'node:fs'
import { fileURLToPath } from 'node:url'

// `virtual:avatar-manifest` — the set of portrait basenames in public/avatars
// (e.g. "the-general", "the-general-thinking"), read at build time. AgentAvatar
// only requests a conventional /avatars/<id>[-state].webp when the file exists,
// so agents without a portrait or expression variant never cost a 404.
function avatarManifest() {
  const ID = 'virtual:avatar-manifest'
  const RESOLVED = '\0' + ID
  return {
    name: 'avatar-manifest',
    resolveId: (id) => (id === ID ? RESOLVED : null),
    load(id) {
      if (id !== RESOLVED) return null
      let names = []
      try {
        names = fs
          .readdirSync(fileURLToPath(new URL('./public/avatars', import.meta.url)))
          .filter((f) => f.endsWith('.webp'))
          .map((f) => f.slice(0, -5))
      } catch {
        /* no avatars folder: every agent uses its fallback */
      }
      return `export default new Set(${JSON.stringify(names.sort())});`
    },
  }
}

export default defineConfig({
  plugins: [react(), avatarManifest()],
  build: {
    rollupOptions: {
      output: {
        // Split the heavy, route-scoped libraries into their own vendor chunks
        // so they stay out of the initial bundle (each is only reached via a
        // lazy route). NOTE: the shared runtime (react, prop-types, zustand,
        // tslib…) MUST be bucketed first — otherwise Rollup co-locates those
        // shared modules inside a heavy vendor chunk, and the eager shell then
        // has to import that whole chunk, pulling three/livekit/flow eager.
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;
          // Shared framework + tiny common runtime used by the eager shell.
          if (/[\\/]node_modules[\\/](react|react-dom|react-router|react-router-dom|scheduler|prop-types|object-assign|use-sync-external-store|zustand|tslib|@tanstack[\\/]|@remix-run[\\/])[\\/]/.test(id)) {
            return 'vendor-react';
          }
          if (/[\\/]node_modules[\\/](three|force-graph|3d-force-graph|react-force-graph[^\\/]*|three-render-objects|three-forcegraph|d3-force-3d|ngraph[^\\/]*|kapsule|accessor-fn)[\\/]/.test(id)) {
            return 'vendor-three';
          }
          if (/[\\/]node_modules[\\/](@livekit|livekit-client)[\\/]/.test(id)) {
            return 'vendor-livekit';
          }
          if (/[\\/]node_modules[\\/](@xyflow|@dagrejs|dagre|classcat)[\\/]/.test(id)) {
            return 'vendor-flow';
          }
          return undefined;
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        // Override to point a dev server at another backend (e.g. a second
        // mock-API instance running a different scenario on another port).
        target: process.env.VITE_PROXY_TARGET || 'http://localhost:8100',
        changeOrigin: true,
      },
    },
  },
})
