import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { tanstackRouter } from '@tanstack/router-vite-plugin';
import tsconfigPaths from 'vite-tsconfig-paths';

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

export default defineConfig({
  root: 'frontend',
  build: {
    outDir: '../frontend/dist',
    emptyOutDir: true,
  },
  plugins: [
    tsconfigPaths(),
    tsconfigPaths({ root: getAgentComponentConfig() }),
    tanstackRouter({
      routesDirectory: './frontend/src/routes',
      disableLogging: true,
      generatedRouteTree: './frontend/src/routeTree.gen.ts',
    }),
    react(),
  ],
  resolve: {
    ...getAgentComponentConditions(),
    alias: {
      '@': '/src',
    },
  },
});
