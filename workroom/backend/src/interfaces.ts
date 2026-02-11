import type { NextFunction, Request, Response } from 'express';
import { z } from 'zod';

export type ExpressNextFunction = NextFunction;

export type ExpressRequest = Request;

export type ErrorResponse = {
  error: {
    code: 'forbidden' | 'internal_error' | 'invalid_request' | 'not_found' | 'rate_limit_exceeded' | 'unauthorized';
    message: string;
  };
};

interface ExpressResponseLocals {
  apiKey?: {
    id: string;
    name: string;
  };
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
    // Maybe email:
    preferred_username: z.string().optional(), // Microsoft OIDC

    groups: z.array(z.string()).optional(),
    roles: z.array(z.string()).optional(),
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

const FeatureFlag = z.object({
  enabled: z.boolean(),
  reason: z.string().nullable(),
});

export const TenantConfig = z.object({
  features: z.object({
    agentAuthoring: FeatureFlag,
    agentConfiguration: FeatureFlag,
    agentDetails: FeatureFlag,
    agentEvals: FeatureFlag,
    deploymentWizard: FeatureFlag,
    developerMode: FeatureFlag,
    documentIntelligence: FeatureFlag,
    mcpServersManagement: FeatureFlag,
    publicAPI: FeatureFlag,
    semanticDataModels: FeatureFlag,
    settings: FeatureFlag,
    userManagement: FeatureFlag,
    workerAgents: FeatureFlag,
  }),
});
export type TenantConfig = z.infer<typeof TenantConfig>;

export const getExpectedLocal = <Key extends keyof ExpressResponseLocals>(
  res: ExpressResponse,
  key: Key,
): NonNullable<ExpressResponseLocals[Key]> => {
  if (typeof res.locals[key] === 'undefined') {
    throw new Error(`Expected local value not set: ${key}`);
  }

  return res.locals[key];
};
