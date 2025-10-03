import { createSparQueryOptions, createSparQuery } from './shared';

/**
 * Get Work Item API URL query
 */
export const workItemAPIUrlQueryKey = () => ['work-item-api-url'];

export const workItemAPIUrlQueryOptions = createSparQueryOptions<object>()(({ sparAPIClient }) => ({
  queryKey: workItemAPIUrlQueryKey(),
  queryFn: async () => {
    const url = await sparAPIClient.getWorkItemAPIURL();
    return url;
  },
}));

export const useWorkItemAPIUrlQuery = createSparQuery(workItemAPIUrlQueryOptions);
