import { expectTypeOf } from 'expect-type';
import { describe, expect, it } from 'vitest';
import { asResult, type Result } from './result.js';

describe('asResult', () => {
  it('handles async functions', async () => {
    const fn = async () => 3;

    const result = await asResult(fn);

    expectTypeOf(result).toEqualTypeOf<Result<number>>();
    expect(result.success).toEqual(true);
    expect((result as Extract<Result<number>, { success: true }>).data).toEqual(3);
  });

  it('unwraps nested results', async () => {
    const fn = () =>
      Promise.resolve({
        success: true,
        data: 5,
      } satisfies Result<number>);

    const result = await asResult(fn);
    expect(result.success).toEqual(true);
    expect((result as Extract<Result<number>, { success: true }>).data).toEqual(5);
  });

  it('passes through the error type', async () => {
    const fn = (): Promise<Result<number, { code: 'test_code'; message: string }>> =>
      Promise.resolve({
        success: false,
        error: {
          code: 'test_code',
          message: 'something',
        },
      });

    const result = await asResult(fn);
    expectTypeOf(result).toEqualTypeOf<
      Result<
        number,
        {
          code: 'test_code';
          message: string;
        }
      >
    >();
  });
});
