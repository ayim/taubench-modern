import { FC, useMemo } from 'react';
import { Box, EmptyState, Progress } from '@sema4ai/components';
import { Illustration } from '../components/Illustration';
import { ButtonLink } from '../common/link';
import { QueryError, ResourceType } from '../queries/shared';
import { getParsedQueryError } from '../lib/error';
import { SparUIRoutes } from '../api/routes';

const DEFAULT_ACTION = {
  to: '/home',
  label: 'Return to Agents',
} as const;

const ACTION_MAP: Record<ResourceType, { to: keyof SparUIRoutes; label: string }> = {
  agent: DEFAULT_ACTION,
  thread: DEFAULT_ACTION,
  data_frame: DEFAULT_ACTION,
  eval: DEFAULT_ACTION,
  feedback: DEFAULT_ACTION,
  semantic_data: DEFAULT_ACTION,
  work_item: DEFAULT_ACTION,
  document_intelligence: DEFAULT_ACTION,
  data_connection: {
    to: '/data-connections',
    label: 'Return to Data Access',
  },
};

const getAction = (resourceType?: ResourceType) => {
  if (typeof resourceType === 'string' && resourceType in ACTION_MAP) {
    return ACTION_MAP[resourceType];
  }
  return DEFAULT_ACTION;
};

const ErrorState: FC<{ error?: QueryError | null }> = ({ error }) => {
  const { title, description, message, resource } = useMemo(() => getParsedQueryError(error), [error]);

  const { to, label } = getAction(resource.type);

  return (
    <Box as="section" display="flex" justifyContent="center" flexDirection="column" maxHeight={960} height="100%">
      <EmptyState
        illustration={<Illustration name={resource.illustration} />}
        title={title}
        description={description}
        errorMessage={message}
        action={
          <ButtonLink to={to} params={{}} round>
            {label}
          </ButtonLink>
        }
      />
    </Box>
  );
};

export const useQueryDataGuard = (queryData: { isLoading: boolean; isError: boolean; error?: QueryError | null }[]) => {
  if (queryData.some(({ isLoading }) => isLoading)) {
    return <Progress variant="page" />;
  }

  /**
   * Report first error
   */
  const queryWithError = queryData.find(({ isError }) => isError);
  if (queryWithError !== undefined) {
    return <ErrorState error={queryWithError.error} />;
  }

  return undefined;
};
