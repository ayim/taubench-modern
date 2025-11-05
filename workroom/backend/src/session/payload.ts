import z from 'zod';
import { OIDCTokens } from '../interfaces.js';

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
        tokens: OIDCTokens,
        userId: z.string().nonempty(),
        userRole: z.string().nonempty(),
      }),
    ]),
    authType: z.literal('oidc'),
  }),
  z.null(),
]);

const isEmpty = (session: Session): boolean => session === null || Object.keys(session).length === 0;

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

export const sessionsEqual = (sessionA: Session, sessionB: Session): boolean => {
  const sessionAEmpty = isEmpty(sessionA);
  const sessionBEmpty = isEmpty(sessionB);
  if (sessionAEmpty && sessionBEmpty) return true;
  if (sessionAEmpty || sessionBEmpty) return false;

  const target1 = structuredClone(sessionA) as unknown as Record<string, string>;
  const target2 = structuredClone(sessionB) as unknown as Record<string, string>;

  delete target1.cookie;
  delete target1.id;
  delete target2.cookie;
  delete target2.id;

  return isEqual(target1, target2);
};
