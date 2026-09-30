import { sveltekit } from "@sveltejs/kit/vite";

export default {
  plugins: [sveltekit()],
  server: { proxy: { "/api": "http://127.0.0.1:8787" } },
};
