import { defineConfig } from "vite";

// `/api` is proxied to the FastAPI backend (`make backend-serve`) in dev and preview.
const backend = process.env.MAPLETRACE_API_URL ?? "http://127.0.0.1:8000";
const apiProxy = {
  "/api": {
    target: backend,
    changeOrigin: true,
    rewrite: (path: string) => path.replace(/^\/api/, ""),
  },
};
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { proxy: apiProxy },
  preview: { proxy: apiProxy },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules")) {
            if (id.includes("@xyflow")) {
              return "xyflow";
            }
            if (id.includes("lucide-react")) {
              return "icons";
            }
            if (id.includes("@tanstack")) {
              return "tanstack";
            }
            return "vendor";
          }
        },
      },
    },
  },
});
