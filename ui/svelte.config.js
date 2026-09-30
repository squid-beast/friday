import adapter from "@sveltejs/adapter-static";

/* friday-ui · svelte.config.js — static build only: the gated Python server
   (integrations/server.py) serves ui/build same-origin; nothing external. */
export default {
  kit: {
    adapter: adapter({ pages: "build", assets: "build", fallback: null, strict: true }),
  },
};
