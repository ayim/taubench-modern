import z from 'zod';
import { Tokens } from '../interfaces.js';

export type Session = z.infer<typeof Session>;
export const Session = z.union([
  z.object({
    auth: z.discriminatedUnion('stage', [
      z.object({
        codeVerifier: z.string(),
        stage: z.literal('auth-callback'),
      }),
      z.object({
        stage: z.literal('authenticated'),
        tokens: Tokens,
      }),
    ]),
    authType: z.literal('oidc'),
  }),
  z.null(),
]);

const isEqual = (obj1: unknown, obj2: unknown): boolean => {
  if (obj1 === obj2) return true;
  if (obj1 == null || obj2 == null) return false;
  if (typeof obj1 !== typeof obj2) return false;

  if (typeof obj1 === 'object' && typeof obj2 === 'object') {
    const keys1 = Object.keys(obj1);
    const keys2 = Object.keys(obj2);

    if (keys1.length !== keys2.length) return false;

    return keys1.every(
      (key) =>
        keys2.includes(key) && isEqual((obj1 as Record<string, unknown>)[key], (obj2 as Record<string, unknown>)[key]),
    );
  }

  return false;
};

export const sessionsEqual = (session1: Session, session2: Session): boolean => {
  if (session1 === null || session2 === null) return false;

  const target1 = structuredClone(session1) as unknown as Record<string, string>;
  const target2 = structuredClone(session2) as unknown as Record<string, string>;

  delete target1.cookie;
  delete target1.id;
  delete target2.cookie;
  delete target2.id;

  return isEqual(target1, target2);
};
