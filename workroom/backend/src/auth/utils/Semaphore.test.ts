import { describe, expect, it } from 'vitest';
import { Semaphore } from './Semaphore.js';

type AsyncValue<Type> = Promise<Type> & { resolve: () => void };

describe('Semaphore', () => {
  const createAsyncValue = <Type>(value: Type): AsyncValue<Type> => {
    let trigger: (value: Type) => void;

    const promise = new Promise<Type>((resolve) => {
      trigger = resolve;
    }) as AsyncValue<Type>;

    promise.resolve = () => {
      trigger(value);
    };

    return promise;
  };

  it('blocks access to an async key', async () => {
    const sema = new Semaphore();
    const value1 = createAsyncValue(1);

    const result1 = sema.use('test', () => value1);
    const result2 = sema.use('test', () => Promise.resolve(2));
    const result3 = sema.use('test', () => Promise.resolve(3));

    value1.resolve();

    expect(await result1).toEqual(1);
    expect(await result2).toEqual(1);
    expect(await result3).toEqual(1);

    const result4 = sema.use('test', () => Promise.resolve(4));
    expect(await result4).toEqual(4);
  });
});
