import { posix } from 'node:path';

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

export function joinUrl(url: string, path: string): string {
  const urlObj = new URL(url);
  urlObj.pathname = posix.join(urlObj.pathname, path);
  return urlObj.toString();
}
