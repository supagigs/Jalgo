import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// Built files are served by Frappe from /assets/jalgo_pos/frontend/
export default defineConfig({
  plugins: [vue()],
  base: '/assets/jalgo_pos/frontend/',
  resolve: { alias: { '@': path.resolve(__dirname, 'src') } },
  build: { outDir: '../jalgo_pos/public/frontend', emptyOutDir: true, target: 'es2019' },
  server: { port: 8080, proxy: { '^/(api|assets|files)': 'http://127.0.0.1:8000' } },
})
