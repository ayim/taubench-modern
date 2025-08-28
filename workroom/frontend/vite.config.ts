import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { tanstackRouter } from '@tanstack/router-vite-plugin';
import tsconfigPaths from 'vite-tsconfig-paths';
import tailwindcss from 'tailwindcss';

const __dirname = dirname(fileURLToPath(import.meta.url));

const getAgentComponentConfig = () => {
  const main = import.meta.resolve('@sema4ai/agent-components');
  const filePath = fileURLToPath(main);
  return filePath.split('dist')[0];
};

const getAgentComponentConditions = () => {
  const main = import.meta.resolve('@sema4ai/agent-components');
  const filePath = fileURLToPath(main);

  // Rely on source only if Agent Components are linked locally
  if (!filePath.includes('node_modules')) {
    return {
      conditions: ['source', 'module', 'import', 'default'],
      dedupe: ['react', '@sema4ai/theme', '@codemirror/state', '@codemirror/lang-json', '@tanstack/react-query'],
    };
  }

  return {};
};

const tenantReplacementPlugin = () => ({
  name: 'tenant-replacement',
  transformIndexHtml(html: string) {
    return html.replace(/DO_NOT_TOUCH_TENANT_ID_PLACEHOLDER/g, 'spar');
  },
});

export default defineConfig({
  root: resolve(__dirname),
  base: './',
  build: {
    outDir: './dist',
    emptyOutDir: true,
    sourcemap: process.env.NODE_ENV !== 'production',
  },
  plugins: [
    tsconfigPaths(),
    tsconfigPaths({ root: getAgentComponentConfig() }),
    tanstackRouter({
      routesDirectory: resolve(__dirname, './src/routes'),
      disableLogging: true,
      generatedRouteTree: resolve(__dirname, './src/routeTree.gen.ts'),
    }),
    react(),
    ...(process.env.NODE_ENV === 'production' ? [] : [tenantReplacementPlugin()]),
  ],
  css: {
    postcss: {
      plugins: [
        tailwindcss({
          config: resolve(__dirname, './tailwind.config.js'),
        }),
      ],
    },
  },
  resolve: {
    ...getAgentComponentConditions(),
    alias: {
      '@': '/src',
    },
  },
});
