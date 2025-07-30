import { applyDelta, Delta } from './patch';

describe('applyDelta', () => {
  it('should apply a concat_string operation to a nested string property', () => {
    const original = {
      user: {
        name: 'Alice',
        bio: 'Loves cats.',
      },
    };

    const delta: Delta = {
      op: 'concat_string',
      path: '/user/bio',
      value: ' Enjoys painting.',
    };

    const result = applyDelta(original, delta);

    expect(result.user.bio).toBe('Loves cats. Enjoys painting.');
    expect(original.user.bio).toBe('Loves cats.');
  });

  it('should apply a concat_string operation with missing intermediate path', () => {
    const original = {};

    const delta: Delta = {
      op: 'concat_string',
      path: '/profile/summary',
      value: 'Hello world',
    };

    const result = applyDelta(original, delta) as {
      profile: { summary: string };
    };

    expect(result.profile.summary).toBe('Hello world');
    expect(original).toEqual({});
  });

  it('should apply a concat_string operation on an array index', () => {
    const original = {
      arr: ['foo', 'bar'],
    };

    const delta: Delta = {
      op: 'concat_string',
      path: '/arr/1',
      value: '_baz',
    };

    const result = applyDelta(original, delta);
    expect(result.arr[1]).toBe('bar_baz');
    expect(original.arr[1]).toBe('bar');
  });

  it('should apply a standard JSON Patch operation (replace)', () => {
    const original = {
      key: 'oldValue',
    };

    const delta: Delta = {
      op: 'replace',
      path: '/key',
      value: 'newValue',
    };

    const result = applyDelta(original, delta);
    expect(result.key).toBe('newValue');
    expect(original.key).toBe('oldValue');
  });

  it('should apply a standard JSON Patch operation (add)', () => {
    const original = {
      list: [1, 2],
    };

    const delta: Delta = {
      op: 'add',
      path: '/list/2',
      value: 3,
    };

    const result = applyDelta(original, delta);
    expect(result.list).toEqual([1, 2, 3]);
    expect(original.list).toEqual([1, 2]);
  });

  it('should not mutate original message', () => {
    const original = { name: 'Jane' };
    const delta: Delta = { op: 'concat_string', path: '/name', value: ' Doe' };
    const result = applyDelta(original, delta);

    expect(result.name).toBe('Jane Doe');
    expect(original.name).toBe('Jane');
  });
});
