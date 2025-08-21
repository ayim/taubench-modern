import type { NextFunction, Request, Response } from 'express';

export type ExpressNextFunction = NextFunction;

export type ExpressRequest = Request;

interface ExpressResponseLocals {
  authSub?: string;
  tenantId?: string;
}
export type ExpressResponse = Response<
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  any,
  ExpressResponseLocals
>;

export const getExpectedLocal = <Key extends keyof ExpressResponseLocals>(
  res: ExpressResponse,
  key: Key,
): NonNullable<ExpressResponseLocals[Key]> => {
  if (typeof res.locals[key] === 'undefined') {
    throw new Error(`Expected local value not set: ${key}`);
  }

  return res.locals[key];
};
