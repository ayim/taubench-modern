type Success<TSuccess> = { success: true; data: TSuccess };
type Failure<TError> = {
  success: false;
  error: TError;
};

export type Result<TSuccess, TError = { code: string; message: string }> = Success<TSuccess> | Failure<TError>;

type ExtractResultValue<T> = T extends Result<infer U, unknown> ? U : T;

/**
 * Convert an async function or value to a Result
 * @example
 *  const result = await asResult(
 *    Promise.resolve(123);
 *  );
 *  // result => {
 *  //   success: true,
 *  //   data: 123
 *  // }
 */
export const asResult = async <ReturnValue, TError = { code: string; message: string }>(
  target: () => Promise<ReturnValue | Result<ReturnValue, TError>>,
  options?: {
    errorCode?: string;
    errorMessage?: string;
  },
): Promise<Result<ExtractResultValue<ReturnValue>, TError>> => {
  try {
    const value = await target();

    if (isResult(value)) {
      if (value.success) {
        return {
          success: true,
          data: value.data,
        } as Result<ExtractResultValue<ReturnValue>, TError>;
      } else {
        return {
          success: false,
          error: value.error as TError,
        };
      }
    }

    return {
      success: true,
      data: value as ExtractResultValue<ReturnValue>,
    };
  } catch (err) {
    const error = err as Error & { code?: unknown };

    return {
      success: false,
      error: {
        code: (options?.errorCode ?? typeof error.code === 'string') ? error.code : 'unexpected_error',
        message: options?.errorMessage ? `${options.errorMessage}: ${error.message}` : error.message,
      } as TError,
    };
  }
};

const isResult = (value: unknown): value is Result<unknown> => {
  return (
    value !== null &&
    typeof value === 'object' &&
    'success' in value &&
    typeof value.success === 'boolean' &&
    ((value.success === true && 'data' in value) || (value.success === false && 'error' in value))
  );
};
