import { MaybeOptionalInit } from 'openapi-fetch';
import { HttpMethod, PathsWithMethod, RequiredKeysOf, SuccessResponseJSON } from 'openapi-typescript-helpers';

export type ApiError = {
  code: string;
  message: string;
};

type ApiResponse<Success> = { data: Success; success: true } | (ApiError & { success: false });

type InitParam<Init> =
  RequiredKeysOf<Init> extends never ? Init & { [key: string]: unknown } : Init & { [key: string]: unknown };

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export interface OpenAPIClient<P extends Record<string, any>> {
  <Path extends PathsWithMethod<P, Method>, Method extends HttpMethod>(
    method: Method,
    path: Path,
    options: InitParam<MaybeOptionalInit<P[Path], Method>>,
  ): Promise<ApiResponse<SuccessResponseJSON<P[Path][Method]>>>;
}
