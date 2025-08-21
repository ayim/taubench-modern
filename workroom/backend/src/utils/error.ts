import { ZodError } from 'zod';

export const formatZodError = (error: ZodError): string => {
  return error.errors.map((e) => `${e.path.join('.')}: ${e.message}`).join(', ');
};
