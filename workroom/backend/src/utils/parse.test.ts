import { describe, expect, it } from 'vitest';
import { caseless, parseCookies } from './parse.js';

describe('caseless', () => {
  it('renders upper-case object properties as lower-case', () => {
    expect(
      caseless({
        test: 123,
        Upper: 456,
        'Content-Type': 'text/plain',
      }),
    ).toEqual({
      test: 123,
      upper: 456,
      'content-type': 'text/plain',
    });
  });
});

describe('parseCookies', () => {
  it('explodes cookie strings into key-value', () => {
    const output = parseCookies('PHPSESSID=298zf09hf012fh2; csrftoken=u32t4o3tb3gg43; _gat=1');
    expect(output).toEqual({
      PHPSESSID: '298zf09hf012fh2',
      csrftoken: 'u32t4o3tb3gg43',
      _gat: '1',
    });
  });

  it('handles empty strings', () => {
    expect(parseCookies('')).toEqual({});
  });

  it('parses Sema4 cookie strings', () => {
    const output = parseCookies(
      's4spar=s%3A4a6786f6-76b7-44b6-9c72-a5f79ad344ec.%2BzgyNtwcuiuZm%2BgiVWvZoShobLVCkrpJTM%2BDZPw0esY',
    );
    expect(output).toEqual({
      s4spar: 's:4a6786f6-76b7-44b6-9c72-a5f79ad344ec.+zgyNtwcuiuZm+giVWvZoShobLVCkrpJTM+DZPw0esY',
    });
  });
});
