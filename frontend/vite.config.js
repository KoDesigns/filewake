import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte()],
  publicDir: 'static',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: false
  },
  server: {
    proxy: {
      '/api': `http://127.0.0.1:${process.env.API_PORT || '8080'}`
    }
  }
});
