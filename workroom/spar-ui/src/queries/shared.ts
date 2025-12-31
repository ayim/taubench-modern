/* eslint-disable @typescript-eslint/no-explicit-any */
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
  McpServer = 'mcp_server',
  SemanticData = 'semantic_data',
  Thread = 'thread',
  WorkItem = 'work_item',
  ThreadFile = 'thread_file',
  Integration = 'integration',
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
  details?: string;
};

export class QueryError extends Error {
  details: Omit<QueryErrorDetails, 'code'> & { code?: QueryErrorCode };

  constructor(message: string, details?: QueryErrorDetails) {
    super(message);
    Object.defineProperty(this, 'message', { value: message, enumerable: true });
    this.name = 'QueryError';
    this.details = {
      type: details?.type,
      // Set code values only to the known ones that are type safe
      code:
        typeof details?.code === 'string' && KnownErrorCodes.has(details.code)
          ? (details.code as QueryErrorCode)
          : undefined,
      resource: details?.resource,
      details: details?.details,
    };
  }
}

export const getSnackbarContent = (error: QueryError): { message: string; variant: 'danger' | 'default' } => {
  const variant = (() => {
    switch (error.details.type) {
      case undefined:
      case 'error':
        return 'danger';
      case 'notice':
        return 'default';
      default:
        error.details.type satisfies never;
        return 'danger';
    }
  })();

  return {
    message: error.message,
    variant,
  };
};

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
  (
    params: Params,
    rest: {
      refetchInterval?: number | ((query: { state: { data: TData | undefined } }) => number | false);
      enabled?: boolean;
      retry?: boolean | number;
      initialData?: TData;
    } = {},
  ) => {
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
