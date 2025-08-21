import { PassThrough } from 'node:stream';
import { exhaustiveCheck } from '@sema4ai/robocloud-shared-utils';
import { parseAgentRequest } from '../api/parsers.js';
import { getRouteBehaviour } from '../api/routing.js';
import type { Configuration } from '../configuration.js';
import { type ExpressRequest, type ExpressResponse } from '../interfaces.js';
import type { MonitoringContext } from '../monitoring/index.js';
import { NO_PROXY_HEADERS } from '../utils/request.js';
import { extractRequestPathAttributes, joinUrl } from '../utils/url.js';

/**
 * Get static agent meta
 * @see {} NOTE that this is dynamic on ACE, and this particular
 *  route is not called
 */
export const createGetAgentMeta = () => (_req: ExpressRequest, res: ExpressResponse) => {
  res.json({
    workroomUi: {
      feedback: { enabled: false },
      conversations: { enabled: true },
      chatInput: { enabled: true },
    },
    canSendFeedback: false,
  });
};

export const createProxyHandler =
  ({
    configuration,
    monitoring,
    rewriteAgentServerPath,
    skipAuthentication = false,
    targetBaseUrl,
  }: {
    configuration: Configuration;
    monitoring: MonitoringContext;
    rewriteAgentServerPath: (currentPath: string, getRequestParameter: (param: string) => string) => string;
    skipAuthentication?: boolean;
    targetBaseUrl: string;
  }) =>
  async (req: ExpressRequest, res: ExpressResponse) => {
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
      authMode: configuration.auth.type,
      authSkip: skipAuthentication,
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

    if (configuration.auth.type !== 'none' && !skipAuthentication) {
      if (!res.locals.authSub) {
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

      const routeBehaviour = getRouteBehaviour({
        configuration,
        route,
        tenantId: configuration.tenant.tenantId,
        userId: res.locals.authSub,
      });

      if (!routeBehaviour.isAllowed) {
        monitoring.logger.error('Route not allowed', {
          requestMethod: req.method,
          requestUrl: requestPathWithQueryStringParameters,
        });

        return res.status(404).send('Not found');
      }

      const signResult = await routeBehaviour.signAgentToken();

      if (!signResult.success) {
        monitoring.logger.error('Token signing for agent server failed', {
          errorName: signResult.error.code,
          errorMessage: signResult.error.message,
        });

        switch (signResult.error.code) {
          case 'invalid_signing_result':
            return res.status(403).send('Forbidden');
          case 'invalid_signing_auth_configuration':
          case 'signing_failed':
            return res.status(500).send('Internal server error');

          default:
            exhaustiveCheck(signResult.error);
        }
      }

      headers.set('Authorization', `Bearer ${signResult.data}`);
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
          const isError = response.status >= 400;
          const decoder = isError ? new TextDecoder() : undefined;
          let errorSnippet = '';
          const maxSnippetBytes = 8 * 1024; // 8KB max in logs
          let collectedBytes = 0;

          try {
            // eslint-disable-next-line no-constant-condition
            while (true) {
              const { done, value } = await reader.read();
              if (done) break;

              if (value) {
                if (isError && collectedBytes < maxSnippetBytes && decoder) {
                  const remaining = maxSnippetBytes - collectedBytes;
                  const slice = value.length > remaining ? value.subarray(0, remaining) : value;
                  errorSnippet += decoder.decode(slice, { stream: true });
                  collectedBytes += slice.length;
                }
                res.write(Buffer.from(value));
              }
            }
            if (isError) {
              const snippetForLog = errorSnippet.length > 0 ? ` bodySnippet="${errorSnippet}"` : '';
              monitoring.logger.error(
                `Agent server responded with error (status=${response.status} statusText=${response.statusText})${snippetForLog}`,
                {
                  requestMethod: req.method,
                  requestUrl: targetUrl,
                },
              );
            }
            res.end();
          } catch (error) {
            monitoring.logger.error('Error during response stream proxying', {
              error: error as Error,
              requestMethod: req.method,
              requestUrl: targetUrl,
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
        if (response.status >= 400) {
          monitoring.logger.error(
            `Agent server responded with error (no body) (status=${response.status} statusText=${response.statusText})`,
            {
              requestMethod: req.method,
              requestUrl: targetUrl,
            },
          );
        }
        res.end();
      }
    } catch (error) {
      monitoring.logger.error('Proxy error', {
        error: error instanceof Error ? error : new Error(`${error}`),
        requestMethod: req.method,
        requestUrl: targetUrl,
      });

      return res.status(502).send('Proxy error');
    }
  };
