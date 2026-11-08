import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// The app calls /api on its own address. In development Vite forwards those calls to the backend, the way Vercel
// does in production, so the session cookies work the same in both.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react()],
    server: {
      proxy: { '/api': { target: env.VITE_API_URL || 'http://127.0.0.1:8010', changeOrigin: true } },
    },
  }
})
