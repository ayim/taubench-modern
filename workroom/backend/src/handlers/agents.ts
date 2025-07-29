import { PassThrough } from 'node:stream';
import type { Request, Response } from 'express';
import { parseAgentRequest } from '../api/parsers.js';
import { isAllowedRoute, signAgentServiceJWTBasedOnRoute } from '../api/routing.js';
import type { Configuration } from '../configuration.js';
import type { MonitoringContext } from '../monitoring/index.js';
import { REQUEST_AUTH_ID_KEY } from '../utils/auth.js';
import { NO_PROXY_HEADERS } from '../utils/request.js';
import { extractRequestPathAttributes, joinUrl } from '../utils/url.js';

/**
 * Get static agent meta
 * @see {} NOTE that this is dynamic on ACE, and this particular
 *  route is not called
 */
export const createGetAgentMeta = () => (_req: Request, res: Response) => {
  res.json({
    workroomUi: {
      feedback: { enabled: false },
      conversations: { enabled: true },
      chatInput: { enabled: true },
    },
    canSendFeedback: false,
  });
};

export const createProxyToAgentServer =
  ({
    configuration,
    monitoring,
    rewriteAgentServerPath,
    targetBaseUrl,
  }: {
    configuration: Configuration;
    monitoring: MonitoringContext;
    rewriteAgentServerPath: (currentPath: string, getRequestParameter: (param: string) => string) => string;
    targetBaseUrl: string;
  }) =>
  async (req: Request, res: Response) => {
    const urlAttributes = extractRequestPathAttributes(req.originalUrl);

    const targetPath = rewriteAgentServerPath(urlAttributes.pathname, (param: string) => {
      const value = req.params[param];
      if (!value) {
        throw new Error(`Failed proxying: Proxied parameter was not found during rewrite: ${param}`);
      }

      return value;
    });

    const targetUrl = `${joinUrl(targetBaseUrl, targetPath)}${urlAttributes.searchParams}`;

    monitoring.logger.info('Proxying agent server request', {
      requestMethod: req.method,
      requestUrl: targetUrl,
    });

    const headers = new Headers();

    // Proxy all valid headers
    for (const [key, value] of Object.entries(req.headers)) {
      if (typeof value !== 'undefined' && NO_PROXY_HEADERS.includes(key) === false) {
        headers.set(key, Array.isArray(value) ? value[0] : value);
      }
    }

    const agentServerUrl = new URL(targetBaseUrl);
    headers.set('Host', req.hostname ?? agentServerUrl.host);

    const clientIP = req.header('x-forwarded-for') || req.header('x-real-ip');
    if (clientIP) {
      headers.set('X-Real-IP', clientIP);
      headers.set('X-Forwarded-For', clientIP);
    }

    if (configuration.auth.type === 'google') {
      const sub = res.locals[REQUEST_AUTH_ID_KEY] as string | undefined;
      if (!sub) {
        throw new Error('Authentication identity not found');
      }

      const requestPathWithQueryStringParameters = `${targetPath}${urlAttributes.searchParams}`;

      const route = parseAgentRequest({
        method: req.method,
        path: requestPathWithQueryStringParameters,
      });

      if (route === null) {
        monitoring.logger.error('Missing agent workroom route', {
          requestMethod: req.method,
          requestUrl: requestPathWithQueryStringParameters,
        });

        return res.status(404).send('Not found');
      }

      if (!isAllowedRoute(route)) {
        monitoring.logger.error('Route not allowed', {
          requestMethod: req.method,
          requestUrl: requestPathWithQueryStringParameters,
        });

        return res.status(404).send('Not found');
      }

      const signTokenResponse = await signAgentServiceJWTBasedOnRoute(
        route,
        { tenantId: 'spar', userId: sub },
        configuration,
      );

      if (!signTokenResponse.success) {
        monitoring.logger.error('Token signing for agent server failed', {
          errorName: signTokenResponse.error.code,
          errorMessage: signTokenResponse.error.message,
        });

        return res.status(500).send('Internal server error');
      }

      if (!signTokenResponse.data.isValid) {
        return res.status(403).send('Forbidden');
      }

      headers.set('Authorization', `Bearer ${signTokenResponse.data.token}`);
    }

    try {
      const fetchOptions: RequestInit = {
        method: req.method,
        headers,
        redirect: 'manual',
      };

      if (req.method === 'POST' || req.method === 'PUT' || req.method === 'PATCH') {
        const passThrough = new PassThrough();
        req.on('error', (err) => {
          passThrough.destroy(err);
        });
        req.pipe(passThrough);

        // @ts-expect-error is not assignable
        fetchOptions.body = passThrough;
        // @ts-expect-error does not exist
        fetchOptions.duplex = 'half';
      }

      const response = await fetch(targetUrl, fetchOptions);

      res.status(response.status);

      for (const [key, value] of response.headers.entries()) {
        if (!['content-encoding', 'content-length', 'transfer-encoding'].includes(key.toLowerCase())) {
          res.set(key, value);
        }
      }

      if (response.body) {
        const reader = response.body.getReader();

        const processStream = async () => {
          try {
            // eslint-disable-next-line no-constant-condition
            while (true) {
              const { done, value } = await reader.read();
              if (done) break;

              if (value) {
                res.write(Buffer.from(value));
              }
            }
            res.end();
          } catch (error) {
            monitoring.logger.error('Error during response stream proxying', {
              error: error as Error,
            });

            if (!res.headersSent) {
              res.status(500).end();
            }
          } finally {
            reader.releaseLock();
          }
        };

        await processStream();
      } else {
        res.end();
      }
    } catch (error) {
      monitoring.logger.error('Agent server proxy error', {
        error: error instanceof Error ? error : new Error(`${error}`),
        requestMethod: req.method,
        requestUrl: targetUrl,
      });

      return res.status(502).send('Proxy error');
    }
  };
