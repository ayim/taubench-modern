import { defineConfig, UserConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import { TanStackRouterVite } from '@tanstack/router-vite-plugin';
import tsconfigPaths from 'vite-tsconfig-paths';
import { fileURLToPath } from 'url';

const getAgentComponentConfig = () => {
  const main = import.meta.resolve('@sema4ai/agent-components');
  const filePath = fileURLToPath(main);
  return filePath.split('dist')[0];
};

const getAgentComponentConditions = (): UserConfig['resolve'] => {
  const main = import.meta.resolve('@sema4ai/agent-components');
  const filePath = fileURLToPath(main);

  // Rely on source only if Agent Compopnents are linked locally
  if (!filePath.includes('node_modules')) {
    return {
      conditions: ['source', 'module', 'import', 'default'],
      dedupe: ['react', '@sema4ai/theme', '@codemirror/state', '@codemirror/lang-json', '@tanstack/react-query'],
    };
  }

  return {};
};

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');

  if (!env.VITE_DEV_SERVER_PORT) {
    throw new Error('Vite dev server port is required');
  }
  if (!env.AGENT_SERVER_PORT) {
    throw new Error('Agent server port is required');
  }
  if (!env.AGENT_SERVER_HOST) {
    throw new Error('Agent server host is required');
  }

  const VITE_DEV_SERVER_PORT = parseInt(env.VITE_DEV_SERVER_PORT, 10);
  const AGENT_SERVER_PORT = parseInt(env.AGENT_SERVER_PORT, 10);
  const AGENT_SERVER_HOST = env.AGENT_SERVER_HOST;

  const isSPAR = env.VITE_DEPLOYMENT_TYPE === 'spar';

  if (isSPAR) {
    console.log('--------------------------------------------------------------');
    console.log('spar DEPLOYMENT TYPE detected');
    console.log(
      `1. Mocking the response of VITE_DEV_WORKROOM_TENANT_LIST_URL (${env.VITE_DEV_WORKROOM_TENANT_LIST_URL})`,
    );
    console.log('2. Mocking the response of /tenants/spar/workroom/meta');
    console.log(`3. Mocking the response of /tenants/spar/agents/AGENT_ID/meta`);
    console.log(
      `4. Proxing all /tenants/spar/agents calls to the locally running agent-server (http://${AGENT_SERVER_HOST}:${AGENT_SERVER_PORT}) - including websocket`,
    );
    console.log('--------------------------------------------------------------');
  }

  return {
    plugins: [
      tsconfigPaths(),
      tsconfigPaths({ root: getAgentComponentConfig() }),
      react(),
      TanStackRouterVite(),
      {
        name: 'mock-router-backend',
        configureServer(server) {
          server.middlewares.use(async (req, res, next) => {
            if (req.url === '/tenants/spar/workroom/meta' && req.method === 'GET') {
              res.setHeader('Content-Type', 'application/json');
              res.end(
                JSON.stringify({
                  features: {
                    documentIntelligence: {
                      enabled: false,
                      reason: 'Doc Intel not available in SPAR YET',
                    },
                    developerMode: {
                      enabled: false,
                      reason: 'Showing action logs not available in SPAR YET',
                    },
                    agentDetails: {
                      enabled: true,
                      reason: null,
                    },
                  },
                }),
              );
              return;
            }
            if (req.url === env.VITE_DEV_WORKROOM_TENANT_LIST_URL && req.method === 'GET') {
              res.setHeader('Content-Type', 'application/json');
              res.end(
                JSON.stringify({
                  data: [
                    {
                      id: 'spar',
                      name: 'SPAR DEV',
                      organization: {
                        id: 'spar_org_id',
                        name: 'SPAR DEV ORG',
                      },
                      environment: {
                        id: '_NOT_USED_IN_SPAR_',
                        url: `http://localhost:${VITE_DEV_SERVER_PORT}`,
                      },
                    },
                  ],
                }),
              );
              return;
            }

            const agentMetaMatch =
              req.url?.match(/^\/tenants\/spar\/workroom\/agents\/([^/]+)\/meta$/) && req.method === 'GET';
            if (agentMetaMatch) {
              res.setHeader('Content-Type', 'application/json');
              res.end(
                JSON.stringify({
                  workroomUi: {
                    feedback: { enabled: false },
                    conversations: { enabled: true },
                    chatInput: { enabled: true },
                  },
                  canSendFeedback: false,
                }),
              );
              return;
            }

            next();
          });
        },
      },
    ],
    resolve: {
      ...getAgentComponentConditions(),
    },
    server: {
      host: '0.0.0.0',
      port: VITE_DEV_SERVER_PORT,
      proxy: {
        '/tenants/spar/agents/api/v2/': {
          target: `http://${AGENT_SERVER_HOST}:${AGENT_SERVER_PORT}`,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/tenants\/spar\/agents/, ''),
        },
        '/tenants/spar/agents/api/v2/runs/': {
          target: `ws://${AGENT_SERVER_HOST}:${AGENT_SERVER_PORT}`,
          changeOrigin: true,
          ws: true,
          rewrite: (path) => path.replace(/^\/tenants\/spar\/agents/, ''),
        },
        // This proxy currently does not work fully: the casing is different for the action servers
        // We should update the original code to preserve the casing and surface it on the regular agent API v2 path
        '^/tenants/spar/workroom/agents/([^/]+)/details$': {
          target: `http://${AGENT_SERVER_HOST}:${AGENT_SERVER_PORT}`,
          changeOrigin: true,
          rewrite: (path) =>
            path.replace(/^\/tenants\/spar\/workroom\/agents\/([^/]+)\/details$/, '/api/v2/agents/$1/agent-details'),
        },
      },
    },
  };
});
