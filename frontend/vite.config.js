import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // The API is called directly through VITE_API_URL so Django's absolute
    // media URLs (logos, banners, galleries) resolve without rewriting.
    open: false,
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
