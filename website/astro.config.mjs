import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  site: "https://arpitdalal.github.io",
  base: "/yt-downloader",
  output: "static",
  vite: {
    plugins: [tailwindcss()],
  },
});
