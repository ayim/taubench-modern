import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { tanstackRouter } from '@tanstack/router-vite-plugin';
import tsconfigPaths from 'vite-tsconfig-paths';
import path from 'node:path';

const tenantReplacementPlugin = () => ({
  name: 'tenant-replacement',
  transformIndexHtml(html: string) {
    return html.replace(/DO_NOT_TOUCH_TENANT_ID_PLACEHOLDER/g, 'spar');
  },
});

export default defineConfig({
  root: path.resolve(__dirname),
  build: {
    outDir: './dist',
    emptyOutDir: true,
    minify: false,
  },
  plugins: [
    tsconfigPaths(),
    tanstackRouter({
      routesDirectory: path.resolve(__dirname, './src/routes'),
      disableLogging: true,
      generatedRouteTree: path.resolve(__dirname, './src/routeTree.gen.ts'),
    }),
    react(),
    ...(process.env.NODE_ENV === 'production' ? [] : [tenantReplacementPlugin()]),
  ],
});
