/* eslint-disable @typescript-eslint/no-explicit-any */
import { useQuery, useMutation, useQueryClient, QueryClient } from '@tanstack/react-query';
import { SparAPIClient } from '../api';
import { useSparUIContext } from '../api/context';

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
  (params: Params, rest: { refetchInterval?: number } = {}) => {
    const { sparAPIClient } = useSparUIContext();
    return useQuery({ ...fn({ ...params, sparAPIClient }), ...rest });
  };

type CommonMutationParams = {
  sparAPIClient: SparAPIClient;
  queryClient: QueryClient;
};

export const createSparMutation =
  <HookParams extends object, MutateParams extends object>() =>
  <TData = any, TError = Error>(
    fn: (params: CommonMutationParams & HookParams) => {
      mutationFn: (variables: MutateParams) => Promise<TData>;
      onSuccess?: (data: TData, variables: MutateParams, hookParams: HookParams) => void;
      onError?: (error: TError, variables: MutateParams, hookParams: HookParams) => void;
    },
  ) =>
  (hookParams: HookParams) => {
    const { sparAPIClient } = useSparUIContext();
    const queryClient = useQueryClient();
    return useMutation({
      ...fn({ sparAPIClient, queryClient, ...hookParams }),
      onSuccess: (data, variables) => {
        fn({ sparAPIClient, queryClient, ...hookParams }).onSuccess?.(data, variables, hookParams);
      },
      onError: (error: TError, variables) => {
        fn({ sparAPIClient, queryClient, ...hookParams }).onError?.(error, variables, hookParams);
      },
    });
  };
