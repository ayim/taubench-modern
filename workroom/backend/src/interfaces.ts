import type { ErrorResponse as WorkRoomErrorResponse } from '@sema4ai/workroom-interface';
import type { NextFunction, Request, Response } from 'express';
import { z } from 'zod';

export type ExpressNextFunction = NextFunction;

export type ExpressRequest = Request;

// SPAR UI expects all endpoints to follow the same shape, inherited from the "workroom interface"
// Because some of the error responses are still handled on ACE / SPCS side (routers), we ensure that all share the same error shape
export type ErrorResponse = WorkRoomErrorResponse;

interface ExpressResponseLocals {
  authSub?: string;
  tenantId?: string;
}
export type ExpressResponse = Response<
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  any,
  ExpressResponseLocals
>;

export type OIDCTokenClaims = z.infer<typeof OIDCTokenClaims>;
export const OIDCTokenClaims = z
  .object({
    iss: z.string().nonempty(),
    sub: z.string().nonempty(),
    aud: z.string().or(z.array(z.string())),
    iat: z.number().int(),
    exp: z.number().int(),
    // Omitted as not needed:
    //   nonce, auth_time, azp
    // Profile scope claims
    name: z.string().optional(),
    given_name: z.string().optional(),
    family_name: z.string().optional(),
    picture: z.url().optional(),
    locale: z.string().optional(),
    // Email scope claims
    email: z.string().email().optional(),
    email_verified: z.boolean().optional(),
  })
  .passthrough();

export type OIDCTokens = z.infer<typeof OIDCTokens>;
export const OIDCTokens = z.object({
  accessToken: z.string().nonempty(),
  claims: OIDCTokenClaims,
  expiresAt: z.number().int(),
  idToken: z.string(),
  oidcUserId: z.string(),
  refreshToken: z.string().nullable(),
  state: z.string().nonempty(),
  tokenType: z.string().nonempty(),
});

export const getExpectedLocal = <Key extends keyof ExpressResponseLocals>(
  res: ExpressResponse,
  key: Key,
): NonNullable<ExpressResponseLocals[Key]> => {
  if (typeof res.locals[key] === 'undefined') {
    throw new Error(`Expected local value not set: ${key}`);
  }

  return res.locals[key];
};
