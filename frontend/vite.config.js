import { defineConfig } from 'vite';
export default defineConfig({ esbuild: { jsx: 'automatic' }, server: { proxy: { '/api': 'http://127.0.0.1:5057', '/assets': 'http://127.0.0.1:5057' } }, build: { outDir: 'dist', assetsDir: 'ui', emptyOutDir: true } });
