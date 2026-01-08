import type { NextFunction, Request, Response } from 'express';
import { createProxyMiddleware, type Options } from 'http-proxy-middleware';
import type { Socket } from 'node:net';
import type { DatabaseClient } from './database.ts';

const PROXY_TIMEOUT = 1000 * 60 * 5; // five minutes

const isExpressResponse = (res: Response | Socket): res is Response => 'status' in res;

type ProxyMiddlewareConfig = {
  db: DatabaseClient;
};

export const createDeploymentProxyMiddleware = ({ db }: ProxyMiddlewareConfig) => {
  const getDeploymentPort = async (deploymentId: string): Promise<number | null> => {
    const result = await db.getDeployment({ id: deploymentId });
    if (!result.success) {
      console.error(`Failed to retrieve port for deployment ${deploymentId}:`, JSON.stringify(result.error));
      return null;
    }

    if (result.data === null) {
      console.error(`Deployment ${deploymentId} does not exist`);
      return null;
    }

    if (result.data.status !== 'running') {
      console.error(`Deployment ${deploymentId} is not running`);
      return null;
    }

    return result.data.port;
  };

  const proxyOptions: Options<Request, Response> = {
    changeOrigin: true,
    timeout: PROXY_TIMEOUT,
    proxyTimeout: PROXY_TIMEOUT,
    router: async (req) => {
      const { deploymentId } = req.params;
      if (!deploymentId) {
        throw new Error('UNEXPECTED: Missing deploymentId in request');
      }

      const port = await getDeploymentPort(deploymentId);
      if (port === null) {
        throw new Error(`Deployment ${deploymentId} not found or has no port assigned`);
      }

      return `http://127.0.0.1:${port}`;
    },
    pathRewrite: (path, req) => {
      const deploymentId = req.params.deploymentId;
      if (!deploymentId) {
        throw new Error('UNEXPECTED: Missing deploymentId in request');
      }

      const prefix = `/deployments/${deploymentId}`;
      return path.startsWith(prefix) ? path.slice(prefix.length) || '/' : path;
    },
    on: {
      error: (err, req, res) => {
        console.error(`Proxy error for ${req.url}:`, err.message);
        if (isExpressResponse(res) && !res.headersSent) {
          res.status(502).json({
            error: {
              code: 'proxy_error',
              message: 'Failed to proxy request to Action Server',
            },
          });
        }
      },
    },
  };

  const proxy = createProxyMiddleware(proxyOptions);

  const middleware = async (req: Request, res: Response, next: NextFunction) => {
    const { deploymentId } = req.params;
    if (!deploymentId) {
      return res.status(400).json({
        error: {
          code: 'missing_deployment_id',
          message: 'Missing deploymentId in request path',
        },
      });
    }

    return proxy(req, res, next);
  };

  return middleware;
};
