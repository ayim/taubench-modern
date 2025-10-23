import type { StorybookConfig } from '@storybook/react-vite';

const config: StorybookConfig = {
  stories: ['../stories/**/*.mdx', '../stories/**/*.stories.@(js|jsx|mjs|ts|tsx)'],
  addons: ['@storybook/addon-links', '@storybook/addon-essentials', '@storybook/addon-interactions'],
  framework: {
    name: '@storybook/react-vite',
    options: {},
  },
  docs: {
    autodocs: 'tag',
  },
  async viteFinal(config) {
    // Configure proxy to avoid CORS issues and enable WebSocket support for localhost:58885
    return {
      ...config,
      server: {
        ...config.server,
        proxy: {
          '/api': {
            target: 'http://localhost:58885',
            changeOrigin: true,
            secure: false,
            ws: true,
            configure: (proxy, options) => {
              proxy.on('error', (err, _req, _res) => {
                console.log('[Proxy] Error:', err);
              });
              proxy.on('proxyReq', (proxyReq, req, _res) => {
                console.log('[Proxy] Sending Request:', req.method, req.url);
              });
              proxy.on('proxyRes', (proxyRes, req, _res) => {
                console.log('[Proxy] Received Response:', proxyRes.statusCode, req.url);
              });
              proxy.on('open', () => {
                console.log('[Proxy] WebSocket connection opened');
              });
              proxy.on('close', (res, socket, head) => {
                console.log('[Proxy] WebSocket connection closed');
              });
            },
          },
        },
      },
    };
  },
};

export default config;
