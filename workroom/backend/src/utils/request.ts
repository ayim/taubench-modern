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
