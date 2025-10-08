import { createSparQueryOptions, createSparQuery } from './shared';

/**
 * Get Work Item API URL query
 */
export const workItemAPIUrlQueryKey = () => ['work-item-api-url'];

export const workItemAPIUrlQueryOptions = createSparQueryOptions<object>()(({ sparAPIClient }) => ({
  queryKey: workItemAPIUrlQueryKey(),
  queryFn: async () => {
    const response = await sparAPIClient.getWorkItemAPIURL();
    
    if (!response.success) {
      throw new Error(response.error.message);
    }
    
    return response.data;
  },
}));

export const useWorkItemAPIUrlQuery = createSparQuery(workItemAPIUrlQueryOptions);
