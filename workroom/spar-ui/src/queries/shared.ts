/* eslint-disable @typescript-eslint/no-explicit-any */
import type { paths } from '@sema4ai/agent-server-interface';
import { useQuery, useMutation, useQueryClient, QueryClient } from '@tanstack/react-query';
import { SparAPIClient } from '../api';
import { useSparUIContext } from '../api/context';

enum QueryErrorCode {
  NotFound = 'not_found',
  Unauthorized = 'unauthorized',
  Forbidden = 'forbidden',
  TooManyRequests = 'too_many_requests',
  MethodNotAllowed = 'method_not_allowed',
  Conflict = 'conflict',
  BadRequest = 'bad_request',
  Unexpected = 'unexpected',
  UnprocessableEntity = 'unprocessable_entity',
  PreconditionFailed = 'precondition_failed',
}

export enum ResourceType {
  Agent = 'agent',
  DataConnection = 'data_connection',
  DataFrame = 'data_frame',
  DocumentIntelligence = 'document_intelligence',
  Evaluation = 'eval',
  Feedback = 'feedback',
  SemanticData = 'semantic_data',
  Thread = 'thread',
  WorkItem = 'work_item',
}

const KnownErrorCodes = new Set<string>(Object.values(QueryErrorCode));
type QueryErrorDetails = {
  type?: 'error' | 'notice';
  /*
   * There might be more codes, this narrows down codes to the known ones
   */
  // eslint-disable-next-line @typescript-eslint/ban-types
  code?: `${QueryErrorCode}` | (string & {});
  resource?: ResourceType;
};

export class QueryError extends Error {
  details: Omit<QueryErrorDetails, 'code'> & { code?: QueryErrorCode };

  constructor(message: string, details?: QueryErrorDetails) {
    super(message);
    this.name = 'QueryError';
    this.details = {
      type: details?.type,
      // Set code values only to the known ones that are type safe
      code:
        typeof details?.code === 'string' && KnownErrorCodes.has(details.code)
          ? (details.code as QueryErrorCode)
          : undefined,
      resource: details?.resource,
    };
  }
}

type CommonQueryParams = {
  sparAPIClient: SparAPIClient;
};

export type ReturnData<TData = any> = TData;

export type SparQueryOptions<Params extends object, TData = ReturnData> = (params: Params & CommonQueryParams) => {
  queryKey: (string | number)[];
  queryFn: () => Promise<TData>;
  initialData?: TData;
};

export function createSparQueryOptions<Params extends object>() {
  return <TData>(
    fn: (params: Params & CommonQueryParams) => {
      queryKey: (string | number)[];
      queryFn: () => Promise<TData>;
      initialData?: TData;
    },
  ): SparQueryOptions<Params, TData> => fn;
}

export const createSparQuery =
  <Params extends object, TData = any>(fn: SparQueryOptions<Params, TData>) =>
  (params: Params, rest: { refetchInterval?: number; enabled?: boolean; retry?: boolean | number } = {}) => {
    const { sparAPIClient } = useSparUIContext();
    return useQuery<TData, QueryError>({ ...fn({ ...params, sparAPIClient }), ...rest });
  };

type CommonMutationParams = {
  sparAPIClient: SparAPIClient;
  queryClient: QueryClient;
};

export const createSparMutation =
  <HookParams extends object, MutateParams extends object>() =>
  <TData = any>(
    fn: (params: CommonMutationParams & HookParams) => {
      mutationFn: (variables: MutateParams) => Promise<TData>;
      onSuccess?: (data: TData, variables: MutateParams, hookParams: HookParams) => void;
      onError?: (error: QueryError, variables: MutateParams, hookParams: HookParams) => void;
    },
  ) =>
  (hookParams: HookParams) => {
    const { sparAPIClient } = useSparUIContext();
    const queryClient = useQueryClient();
    return useMutation<TData, QueryError, MutateParams>({
      ...fn({ sparAPIClient, queryClient, ...hookParams }),
      onSuccess: (data, variables) => {
        fn({ sparAPIClient, queryClient, ...hookParams }).onSuccess?.(data, variables, hookParams);
      },
      onError: (error: QueryError, variables) => {
        fn({ sparAPIClient, queryClient, ...hookParams }).onError?.(error, variables, hookParams);
      },
    });
  };

type HttpMethod = 'get' | 'put' | 'post' | 'delete' | 'options' | 'head' | 'patch' | 'trace';

type HasMethodForPath<T, K extends keyof T> = K extends keyof T
  ? Pick<T, K> extends Required<Pick<T, K>>
    ? true
    : false
  : false;

type RoutesForMethod<M extends HttpMethod> = {
  [R in keyof paths]: HasMethodForPath<paths[R], M> extends true ? R : never;
}[keyof paths];

export type ServerResponse<
  TMethod extends HttpMethod,
  TAPIRoute extends RoutesForMethod<TMethod> = never,
> = paths[TAPIRoute][TMethod] extends { responses: { 200: { content: { 'application/json': unknown } } } }
  ? paths[TAPIRoute][TMethod]['responses'][200]['content']['application/json']
  : never;

export type ServerRequest<
  TMethod extends HttpMethod,
  TAPIRoute extends RoutesForMethod<TMethod> = never,
  TArg extends 'requestBody' | 'query' | 'path' = never,
> = TArg extends keyof paths[TAPIRoute][TMethod]
  ? paths[TAPIRoute][TMethod][TArg] extends { content: { 'application/json': infer Body } }
    ? Body
    : never
  : TArg extends 'path'
    ? 'parameters' extends keyof paths[TAPIRoute][TMethod]
      ? paths[TAPIRoute][TMethod]['parameters'] extends { path?: infer Path }
        ? Path
        : never
      : never
    : TArg extends 'query'
      ? 'parameters' extends keyof paths[TAPIRoute][TMethod]
        ? paths[TAPIRoute][TMethod]['parameters'] extends { query?: infer Query }
          ? Query
          : never
        : never
      : never;
