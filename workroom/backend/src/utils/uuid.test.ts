import { describe, expect, it } from 'vitest';
import z from 'zod';
import { stringToUUID } from './uuid.js';

describe('stringToUUID', () => {
  const uuid = z.uuid();

  it('converts strings to valid UUIDs', () => {
    const randomUUID = stringToUUID(Date.now().toString());
    const uuidResult = uuid.safeParse(randomUUID);

    expect(uuidResult).toEqual({
      success: true,
      data: randomUUID,
    });
  });

  it('remains stable', () => {
    expect(stringToUUID('this is a stable string')).toEqual('a4cb2081-9197-59f5-8d98-4cbac6db2df9');
    expect(stringToUUID('')).toEqual('da39a3ee-5e6b-5b0d-b255-bfef95601890');
    expect(stringToUUID(' ')).toEqual('b858cb28-2617-5b09-96d9-60215c8e84d1');
    expect(stringToUUID('ปลา')).toEqual('241ba57e-92ed-5568-9b5b-4dfbe59337a5');
  });
});
