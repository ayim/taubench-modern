import { useCallback, useEffect, useRef, useState, Dispatch, SetStateAction, useContext } from 'react';
import { useLocalStorage } from '@sema4ai/components';
import { QuerySettings } from '@sema4ai/layouts';
import { SparUIContext } from '../../api/context';
import { WorkItemStatus } from '../../queries';
import { WORK_ITEM_STATUS_VALUES } from '../../constants/workItemStatus';

type UsePersistedQueryParams = {
  storageKey: string;
  agentsById: Map<string, string>;
  agentsByName: Map<string, string>;
};

type UsePersistedQueryResult = {
  query: Partial<QuerySettings>;
  setQuery: Dispatch<SetStateAction<Partial<QuerySettings>>>;
};

const EMPTY_QUERY: Partial<QuerySettings> = {
  filters: { status: [], agent_name: [] },
  search: '',
  page: 0,
  size: 50,
};

const normalizeStatusArray = (status: string | string[]): string[] => {
  const statusArray = Array.isArray(status) ? status : [status];
  return statusArray.filter(
    (s): s is string => typeof s === 'string' && WORK_ITEM_STATUS_VALUES.includes(s as WorkItemStatus),
  );
};

const convertUrlToQuery = (
  urlParams: Record<string, unknown>,
  agentsById: Map<string, string>,
): Partial<QuerySettings> => {
  const filters: Record<string, string[]> = { status: [], agent_name: [] };

  const status = urlParams.status as string | string[] | undefined;
  if (status) {
    filters.status = normalizeStatusArray(status);
  }

  const agent = urlParams.agent as string | undefined;
  if (agent) {
    const agentName = agentsById.get(agent);
    if (agentName) {
      filters.agent_name = [agentName];
    }
  }

  const search = urlParams.search as string | undefined;
  const page = urlParams.page as number | undefined;

  return {
    filters,
    search: search || '',
    page: page && page > 0 ? page : 0,
  };
};

const convertQueryToUrl = (
  query: Partial<QuerySettings>,
  agentsByName: Map<string, string>,
): Record<string, unknown> => {
  const urlParams: Record<string, unknown> = {};

  if (query.filters?.status?.length) {
    urlParams.status = query.filters.status.length === 1 ? query.filters.status[0] : query.filters.status;
  }

  if (query.filters?.agent_name?.length) {
    const agentId = agentsByName.get(query.filters.agent_name[0]);
    if (agentId) {
      urlParams.agent = agentId;
    }
  }

  if (query.search) {
    urlParams.search = query.search;
  }

  if (query.page && query.page > 0) {
    urlParams.page = query.page;
  }

  return urlParams;
};

const hasAnyQueryParams = (query: Partial<QuerySettings>): boolean => {
  return Boolean(
    query.filters?.status?.length ||
      query.filters?.agent_name?.length ||
      query.search ||
      (query.page && query.page > 0),
  );
};

export const usePersistedQuery = ({
  storageKey,
  agentsById,
  agentsByName,
}: UsePersistedQueryParams): UsePersistedQueryResult => {
  const { sparAPIClient } = useContext(SparUIContext);
  const urlSearchParams = sparAPIClient.useSearchParamsFn();
  const { storageValue: localStorageQuery, setStorageValue: setLocalStorageQuery } = useLocalStorage<
    Partial<QuerySettings>
  >({
    key: storageKey,
    defaultValue: EMPTY_QUERY,
  });

  const [query, setQueryState] = useState<Partial<QuerySettings>>(localStorageQuery ?? EMPTY_QUERY);
  const hasInitialized = useRef(false);

  useEffect(() => {
    if (agentsById.size === 0 || hasInitialized.current) return;
    hasInitialized.current = true;

    const urlQuery = convertUrlToQuery(urlSearchParams, agentsById);
    const hasUrlParams = hasAnyQueryParams(urlQuery);

    if (hasUrlParams) {
      const mergedQuery = { ...EMPTY_QUERY, ...urlQuery };
      setQueryState(mergedQuery);
      setLocalStorageQuery(mergedQuery);
      return;
    }

    if (hasAnyQueryParams(localStorageQuery ?? {})) {
      const urlParams = convertQueryToUrl(localStorageQuery ?? {}, agentsByName);
      sparAPIClient.navigate({
        to: '/workItems',
        params: {},
        search: urlParams,
      });
    }
  }, [agentsById.size, agentsById, agentsByName, localStorageQuery, setLocalStorageQuery, urlSearchParams]);

  const setQuery: Dispatch<SetStateAction<Partial<QuerySettings>>> = useCallback(
    (queryOrUpdater) => {
      setQueryState((previousQuery) => {
        const newQuery = typeof queryOrUpdater === 'function' ? queryOrUpdater(previousQuery) : queryOrUpdater;

        const urlParams = convertQueryToUrl(newQuery, agentsByName);
        sparAPIClient.navigate({
          to: '/workItems',
          params: {},
          search: urlParams,
        });
        setLocalStorageQuery(newQuery);

        return newQuery;
      });
    },
    [agentsByName, setLocalStorageQuery],
  );

  return { query, setQuery };
};
