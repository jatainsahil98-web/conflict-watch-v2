import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";
import { viteSingleFile } from "vite-plugin-singlefile";
import { resolve } from "path";

export default defineConfig(({ mode }) => {
  const single = mode === "single";
  return {
    base: "./",
    resolve: { alias: single ? { "./data-source": resolve(__dirname, "src/data-source.inline.ts") } : {} },
    build: single
      ? { outDir: "dist-single", emptyOutDir: true, assetsInlineLimit: 100_000_000, chunkSizeWarningLimit: 5000 }
      : { outDir: "dist", emptyOutDir: true, chunkSizeWarningLimit: 1500,
          rollupOptions: { input: { main: resolve(__dirname, "index.html"), console: resolve(__dirname, "console/index.html") } } },
    publicDir: single ? false : "public",
    plugins: single
      ? [viteSingleFile()]
      : [VitePWA({
          registerType: "autoUpdate", injectRegister: null,
          includeAssets: ["icons/*.png", "icons/*.svg"],
          workbox: { globPatterns: ["**/*.{js,css,html,json,geojson,woff2,png,svg}"], maximumFileSizeToCacheInBytes: 6_000_000,
                     navigateFallbackDenylist: [/^\/console/] },
          manifest: {
            name: "Conflict EW Console", short_name: "Conflict EW", start_url: "./console/index.html", scope: "./",
            display: "standalone", background_color: "#05070A", theme_color: "#05070A",
            description: "Four-theatre conflict forecasting, early warning and India-impact console.",
            icons: [{ src: "icons/icon-192.png", sizes: "192x192", type: "image/png" },
                    { src: "icons/icon-512.png", sizes: "512x512", type: "image/png" },
                    { src: "icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" }],
          },
        })],
  };
});
