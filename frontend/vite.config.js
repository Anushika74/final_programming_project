import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite configuration. The dev server proxies API + WebSocket calls to the
// FastAPI backend so the frontend can use relative URLs in development.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/ws": {
        target: "ws://localhost:8000",
        ws: true,
      },
    },
  },
});
