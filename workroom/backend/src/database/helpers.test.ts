import { describe, expect, it } from 'vitest';
import { omitProperties } from './helpers.js';

describe('omitProperties', () => {
  it('omits properties from objects', () => {
    const initial = {
      a: true,
      b: 1,
      c: false,
      d: null,
    };

    const result = omitProperties(initial, ['b', 'c']);
    expect(result).toEqual({ a: true, d: null });

    type Result = keyof typeof result;
    type Expected = 'a' | 'd';
    const _typeCheck: Expected = 'a' satisfies Result;
  });
});
