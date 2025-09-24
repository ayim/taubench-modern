import { describe, expect, it } from 'vitest';
import type { Result } from './result.js';
import { extractRequestPathAttributes, joinUrl, safeParseUrl } from './url.js';

describe('extractRequestPathAttributes', () => {
  it.each([
    ['http://localhost:9000/start/1/2/', '/start/1/2/'],
    ['https://test.sema4.ai/one-two/three', '/one-two/three'],
    ['https://test.sema4.ai', '/'],
    ['/', '/'],
    ['/test-1/2', '/test-1/2'],
  ])('extracts correct pathname from %s', (url, pathname) => {
    expect(extractRequestPathAttributes(url)).toHaveProperty('pathname', pathname);
  });

  it.each([
    ['http://localhost:9000?test=abc&def=123', '?test=abc&def=123'],
    ['https://test.sema4.ai', ''],
    ['https://test.sema4.ai?a', '?a'],
    ['/test?test', '?test'],
  ])('extracts correct search string from %s', (url, search) => {
    expect(extractRequestPathAttributes(url)).toHaveProperty('searchParams', search);
  });
});

describe('joinUrl', () => {
  it.each([
    [['https://test.com', 'a', 'b'], 'https://test.com/a/b'],
    [['https://test.com/', '/some-path/nested/'], 'https://test.com/some-path/nested/'],
  ])('joins the following components: %a', (components, url) => {
    // @ts-expect-error Must have type tuple
    expect(joinUrl(...components)).toEqual(url);
  });
});

describe('safeParseUrl', () => {
  it.each([['http://test.com'], ['https://test.com/sub-page/?abc-123']])('handles valid URL: %s', (url) => {
    const parseResult = safeParseUrl(url);
    expect(parseResult.success).toEqual(true);
  });

  it('handles invalid URLs', () => {
    const parseResult = safeParseUrl('/invalid');
    expect(parseResult.success).toEqual(false);

    const badResult = parseResult as Extract<Result<URL>, { success: false }>;
    expect(badResult.error.code).toEqual('invalid_url');
    expect(badResult.error.message).toContain('/invalid');
  });
});
