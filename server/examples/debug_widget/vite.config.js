import path from 'path';
import { defineConfig } from 'vite';
import { viteSingleFile } from 'vite-plugin-singlefile';
import anywidget from '@anywidget/vite';

export default defineConfig({
  mode: 'development',
  plugins: [anywidget(), viteSingleFile()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    cors: {
      origin: '*',
      methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
      allowedHeaders: ['Content-Type', 'Authorization'],
    },
  },
  build: {
    outDir: 'static',
    lib: {
      entry: ['src/index.tsx'],
      formats: ['es'],
      name: 'widget',
    },
    rollupOptions: {
      output: {
        manualChunks: undefined,
      },
    },
  },
  define: {
    'process.env': {},
  },
});
