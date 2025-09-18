import { describe, expect, it } from 'vitest';
import { extractHeadersFromRequest, getRequestBaseUrl } from './request.js';
import type { ExpressRequest } from '../interfaces.js';

describe('extractHeadersFromRequest', () => {
  it('returns lower-case headers', () => {
    expect(
      extractHeadersFromRequest({
        'Content-Type': 'text/plain',
        Accept: 'text/html',
        'content-size': '1234',
      }),
    ).toEqual({
      'content-type': 'text/plain',
      accept: 'text/html',
      'content-size': '1234',
    });
  });
});

describe('getRequestBaseUrl', () => {
  const req = {
    get(value: string) {
      switch (value) {
        case 'host':
          return 'test.sema4.ai';
        default:
          throw new Error(`Unimplemented: ${value}`);
      }
    },
    protocol: 'https',
  } as ExpressRequest;

  it('returns the expected base URL for a request', () => {
    const url = getRequestBaseUrl(req);

    expect(url).toEqual('https://test.sema4.ai');
  });
});
