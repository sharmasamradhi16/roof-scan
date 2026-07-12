import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // This is fine to keep, it lets you view the app on your phone via local Wi-Fi
    port: 5173,
  }
})