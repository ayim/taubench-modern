import type http from 'node:http';
import Stream from 'node:stream';
import { exhaustiveCheck } from '@sema4ai/shared-utils';
import { WebSocket, WebSocketServer } from 'ws';
import { parseAgentRequest } from '../api/parsers.js';
import { getRouteBehaviour } from '../api/routing.js';
import type { AuthManager } from '../auth/AuthManager.js';
import type { Configuration } from '../configuration.js';
import { extractAuthenticatedUserIdentity } from '../middleware/auth/index.js';
import type { MonitoringContext } from '../monitoring/index.js';
import type { SessionManager } from '../session/sessionManager.js';
import { extractHeadersFromRequest, NO_PROXY_HEADERS, NO_PROXY_WEBSOCKET_HEADERS } from '../utils/request.js';
import { extractRequestPathAttributes, joinUrl } from '../utils/url.js';

/**
 * Start websocket proxying
 */
export const initializeWebSocketProxying = ({
  authManager,
  configuration,
  monitoring,
  rewriteAgentServerPath,
  sessionManager,
  targetBaseUrl,
}: {
  authManager: AuthManager;
  configuration: Configuration;
  monitoring: MonitoringContext;
  rewriteAgentServerPath: (currentPath: string) => string;
  sessionManager: SessionManager;
  targetBaseUrl: string;
}) => {
  const webSocketServer = new WebSocketServer({
    noServer: true,
    perMessageDeflate: false,
  });

  const shutdownPair = ({ workroomWs, agentBackendWs }: { workroomWs: WebSocket; agentBackendWs: WebSocket }): void => {
    try {
      workroomWs.close();
    } catch (e) {
      const error = e as Error;
      monitoring.logger.error('failed_to_close_workroom_websocket', { error });
    }
    try {
      agentBackendWs.close();
    } catch (e) {
      const error = e as Error;
      monitoring.logger.error('failed_to_close_agent_websocket', { error });
    }
  };

  /**
   * Handle upgrading a websocket connection
   * @see {} Not used for ACE
   */
  const handleWebsocketUpgrade = async (
    req: http.IncomingMessage,
    socket: Stream.Duplex,
    head: Buffer<ArrayBufferLike>,
  ) => {
    const unauthorizedAccess = () => {
      socket.write('HTTP/1.1 401 Unauthorized\r\n\r\n');
      socket.destroy();
    };

    const forbiddenAccess = () => {
      socket.write('HTTP/1.1 403 Unauthorized\r\n\r\n');
      socket.destroy();
    };

    const internalServerError = () => {
      socket.write('HTTP/1.1 500 Internal Server Error\r\n\r\n');
      socket.destroy();
    };

    const notFoundError = () => {
      socket.write('HTTP/1.1 404 Not Found\r\n\r\n');
      socket.destroy();
    };

    monitoring.logger.info('Upgrade websocket connection', {
      requestUrl: req.url,
    });

    if (!req.url) {
      monitoring.logger.error('No request URL found for websocket upgrade', {
        requestMethod: req.method,
        requestUrl: req.url,
      });

      return internalServerError();
    }
    if (!req.method) {
      monitoring.logger.error('No request method found for websocket upgrade', {
        requestMethod: req.method,
        requestUrl: req.url,
      });

      return internalServerError();
    }

    const urlAttributes = extractRequestPathAttributes(req.url);
    const targetPath = rewriteAgentServerPath(urlAttributes.pathname);

    const headers: Record<string, string> = {};
    // Proxy all valid headers
    for (const [key, value] of Object.entries(req.headers)) {
      if (
        typeof value !== 'undefined' &&
        NO_PROXY_HEADERS.includes(key) === false &&
        NO_PROXY_WEBSOCKET_HEADERS.includes(key) === false
      ) {
        headers[key] = Array.isArray(value) ? value[0] : value;
      }
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

      return notFoundError();
    }

    if (configuration.auth.type !== 'none') {
      const userIdentityResult = await extractAuthenticatedUserIdentity({
        authManager,
        configuration,
        headers: extractHeadersFromRequest(req.headers),
        monitoring,
        permissions: [],
        sessionManager,
      });

      if (!userIdentityResult.success) {
        monitoring.logger.error('Websocket upgrade failed: User identity resolution failed', {
          errorName: userIdentityResult.error.code,
          errorMessage: userIdentityResult.error.message,
          requestMethod: req.method,
          requestUrl: req.url,
        });

        switch (userIdentityResult.error.code) {
          case 'unauthorized':
            return unauthorizedAccess();
          case 'pending':
          case 'expired': // Should never get here
          case 'forbidden':
            return forbiddenAccess();
          case 'misconfigured':
            return internalServerError();

          default:
            exhaustiveCheck(userIdentityResult.error);
        }
      }

      if (!userIdentityResult.data.userId) {
        monitoring.logger.error('Websocket upgrade failed: No user ID', {
          requestMethod: req.method,
          requestUrl: req.url,
        });

        return unauthorizedAccess();
      }

      const routeBehaviour = getRouteBehaviour({
        configuration,
        route,
        tenantId: configuration.tenant.tenantId,
        userId: userIdentityResult.data.userId,
      });

      if (!routeBehaviour.isAllowed) {
        monitoring.logger.error('Route not allowed', {
          requestMethod: req.method,
          requestUrl: requestPathWithQueryStringParameters,
        });

        return notFoundError();
      }

      const signResult = await routeBehaviour.signAgentToken();

      if (!signResult.success) {
        monitoring.logger.error('Agent server token signing invalid', {
          errorName: signResult.error.code,
          errorMessage: signResult.error.message,
        });

        switch (signResult.error.code) {
          case 'invalid_signing_result':
            return forbiddenAccess();
          case 'invalid_signing_auth_configuration':
          case 'signing_failed':
            return internalServerError();

          default:
            exhaustiveCheck(signResult.error);
        }
      }

      headers['authorization'] = `Bearer ${signResult.data}`;
    }

    const targetUrl = `${joinUrl(targetBaseUrl, targetPath)}${urlAttributes.searchParams}`
      .replace('http://', 'ws://')
      .replace('https://', 'wss://');

    monitoring.logger.info('Connecting upstream websocket', {
      requestUrl: targetUrl,
    });

    webSocketServer.handleUpgrade(req, socket, head, (wsClient) => {
      webSocketServer.emit('connection', wsClient, {
        agentStreamWebsocketURL: targetUrl,
        headers,
      });
    });
  };

  webSocketServer.on(
    'connection',
    (
      workroomWs: WebSocket,
      {
        agentStreamWebsocketURL,
        headers,
      }: {
        agentStreamWebsocketURL: string;
        headers: {
          authorization?: string;
        };
      },
    ) => {
      monitoring.logger.info('Proxying agent server websocket connection', {
        requestUrl: agentStreamWebsocketURL,
      });

      const agentBackendWs = new WebSocket(agentStreamWebsocketURL, {
        headers,
        perMessageDeflate: false,
      });

      const bufferedOutgoingMessages: Array<{
        binary: boolean;
        data: WebSocket.RawData;
      }> = [];
      const bufferedIncomingMessages: Array<{
        binary: boolean;
        data: WebSocket.RawData;
      }> = [];

      const reconcileBufferedMessages = () => {
        if (agentBackendWs.readyState === WebSocket.OPEN && bufferedOutgoingMessages.length > 0) {
          // Send outgoing messages
          for (const payload of bufferedOutgoingMessages) {
            agentBackendWs.send(payload.data, { binary: payload.binary });
          }

          monitoring.logger.info('Sent buffered outgoing websocket messages', {
            count: bufferedOutgoingMessages.length,
          });

          bufferedOutgoingMessages.splice(0, Infinity);
        }

        if (workroomWs.readyState === WebSocket.OPEN && bufferedIncomingMessages.length > 0) {
          // Send incoming messages
          for (const payload of bufferedIncomingMessages) {
            workroomWs.send(payload.data, { binary: payload.binary });
          }

          monitoring.logger.info('Sent buffered incoming websocket messages', {
            count: bufferedIncomingMessages.length,
          });

          bufferedIncomingMessages.splice(0, Infinity);
        }
      };

      workroomWs.on('open', reconcileBufferedMessages);
      agentBackendWs.on('open', reconcileBufferedMessages);

      // Work Room -> Agent Backend
      workroomWs.on('message', (data, isBinary) => {
        if (agentBackendWs.readyState === WebSocket.OPEN) {
          agentBackendWs.send(data, { binary: isBinary });
        } else {
          bufferedOutgoingMessages.push({ binary: isBinary, data });
        }
      });

      // Agent Backend -> Work Room
      agentBackendWs.on('message', (data, isBinary) => {
        if (workroomWs.readyState === WebSocket.OPEN) {
          workroomWs.send(data, { binary: isBinary });
        } else {
          bufferedIncomingMessages.push({ binary: isBinary, data });
        }
      });

      const shutdown = () => shutdownPair({ workroomWs, agentBackendWs });
      workroomWs.on('close', shutdown).on('error', shutdown);
      agentBackendWs.on('close', shutdown).on('error', shutdown);
    },
  );

  return {
    handleWebsocketUpgrade,
  };
};
