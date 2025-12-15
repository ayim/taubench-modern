import { prettifyError, ZodError } from 'zod';

/**
 * Force a thrown value to be an Error
 * @param item A thrown error of some form
 * @example
 *  try {
 *    // Some error-prone code
 *  } catch (err) {
 *    const error = asError(err);
 *  }
 */
export const asError = (item: unknown): Error => {
  if (!(item instanceof Error)) {
    return new Error(`${item}`);
  }

  return item;
};

/**
 * Format a Zod error as a string for better readability while logging
 */
export const formatZodError = (error: ZodError): string => {
  return prettifyError(error);
};
