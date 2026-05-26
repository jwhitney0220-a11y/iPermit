import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// Dev server on 5173 (forwarded by the devcontainer); proxy /api to the
// FastAPI backend on 8000 so the SPA and API share an origin in development.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
});
