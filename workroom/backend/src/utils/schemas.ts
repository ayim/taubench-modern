import z from 'zod';

export type SignedTokenRequest = z.infer<typeof SignedTokenRequest>;
export const SignedTokenRequest = z.object({
  userId: z.string().min(1),
});
