import type { IncomingHttpHeaders } from 'node:http';
import type { ExpressRequest } from '../interfaces.js';

export const NO_PROXY_HEADERS = [
  'accept-encoding',
  'content-length',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'proxy-connection',
  'te',
  'trailer',
  'transfer-encoding',
];

export const NO_PROXY_WEBSOCKET_HEADERS = [
  'sec-websocket-extensions',
  'sec-websocket-key',
  'sec-websocket-protocol',
  'sec-websocket-version',
];

export const extractHeadersFromRequest = (
  reqHeaders: Record<string, string | string[] | undefined>,
): Record<string, string> => {
  const headers: Record<string, string> = {};
  for (const [key, value] of Object.entries(reqHeaders)) {
    headers[key.toLowerCase()] = `${value}`;
  }

  return headers;
};

export const getRequestBaseUrl = (req: ExpressRequest): string => {
  return `${req.protocol}://${req.get('host')}`;
};

export const headersToObject = (
  headers: IncomingHttpHeaders | Headers | Record<string, string>,
): Record<string, string> => {
  const webHeaders = (() => {
    if (headers instanceof Headers) {
      return headers;
    }

    const output = new Headers();

    for (const [key, value] of Object.entries(headers)) {
      if (typeof value === 'string') {
        output.set(key, value);
      } else if (Array.isArray(value)) {
        value.forEach((v) => output.append(key, v));
      }
    }

    return output;
  })();

  return Object.fromEntries(webHeaders.entries());
};
