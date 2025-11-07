import { prettifyError, ZodError } from 'zod';

/**
 * Format a Zod error as a string for better readability while logging
 */
export const formatZodError = (error: ZodError): string => {
  return prettifyError(error);
};
