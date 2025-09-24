import { posix } from 'node:path';
import type { Result } from './result.js';

/**
 * Extract common attributes from a request URL that is usually
 * just a path and query string. This method overwrites the base
 * URL as it expects it to be absent.
 * @param originalUrl The request URL, usually `req.originalUrl`
 *  in Express
 * @example
 *  const { pathname } = extractRequestPathAttributes(req.originalUrl);
 */
export const extractRequestPathAttributes = (
  originalUrl: string,
): {
  pathname: string;
  searchParams: `?{string}` | '';
} => {
  const url = new URL(originalUrl, 'http://localhost');

  return {
    pathname: url.pathname,
    searchParams: url.search.length === 0 ? '' : (decodeURIComponent(url.search) as `?{string}`),
  };
};

export const joinUrl = (baseUrl: string, ...parts: Array<string>): string => {
  const urlObj = new URL(baseUrl);
  urlObj.pathname = posix.join(urlObj.pathname, ...parts);
  return urlObj.toString();
};

export const safeParseUrl = (url: string): Result<URL, { code: 'invalid_url' | 'unknown'; message: string }> => {
  try {
    const output = new URL(url);

    return {
      success: true,
      data: output,
    };
  } catch (err) {
    const error = err as Error & { code?: string };

    return {
      success: false,
      error:
        error.code === 'ERR_INVALID_URL'
          ? {
              code: 'invalid_url',
              message: `Invalid URL "${url}"`,
            }
          : {
              code: 'unknown',
              message: `Unexpected error parsing URL "${url}": ${error.message}`,
            },
    };
  }
};
