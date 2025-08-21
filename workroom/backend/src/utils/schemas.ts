import z from 'zod';

export type SignedTokenRequest = z.infer<typeof SignedTokenRequest>;
export const SignedTokenRequest = z.object({
  userId: z.string().min(1),
});

export type TenantRequestParameters = z.infer<typeof TenantRequestParameters>;
export const TenantRequestParameters = z.object({
  tenantId: z
    .string()
    .min(1)
    .regex(/^[^\s]+$/),
});

export type ControlPlaneUserResponse = z.infer<typeof ControlPlaneUserResponse>;
export const ControlPlaneUserResponse = z.object({
  userId: z.string(),
});
