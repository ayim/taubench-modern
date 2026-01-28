import { WorkItemsNavigationContext } from '~/lib/navigation';

/**
 * Gets current URL search parameters as an object
 */
export const getUrlSearchParams = (): Record<string, string> => {
  if (typeof window === 'undefined') return {};

  const params = new URLSearchParams(window.location.search);
  const result: Record<string, string> = {};

  params.forEach((value, key) => {
    result[key] = value;
  });

  return result;
};

/**
 * Creates a navigation context for work items with current URL parameters
 */
export const createWorkItemsNavigationContext = (
  from: 'workItems',
  tab: 'all' | 'overview',
  additionalParams?: Record<string, string>,
): WorkItemsNavigationContext | null => {
  try {
    const urlParams = getUrlSearchParams();

    return {
      from,
      tab,
      timestamp: Date.now(),
      ...(urlParams.agent && { agent: urlParams.agent }),
      ...(urlParams.status && { status: urlParams.status }),
      ...(urlParams.search && { search: urlParams.search }),
      ...(urlParams.page && { page: urlParams.page }),
      ...additionalParams,
    };
  } catch {
    return null;
  }
};
