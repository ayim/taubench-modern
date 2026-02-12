/* eslint-disable import/no-extraneous-dependencies */
import { FC, ReactNode } from 'react';
import {
  QueryClient,
  QueryClientProvider as QueryClientProviderBase,
  QueryCache,
  MutationCache,
} from '@tanstack/react-query';

export const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error, query) => {
      // eslint-disable-next-line no-console
      console.error(`Query failed (key: ${JSON.stringify(query.queryKey)}):`, error);
    },
  }),
  mutationCache: new MutationCache({
    onError: (error) => {
      // eslint-disable-next-line no-console
      console.error('Mutation failed:', error);
    },
  }),
});

type Props = {
  children?: ReactNode;
};

export const QueryClientProvider: FC<Props> = ({ children }) => {
  return <QueryClientProviderBase client={queryClient}>{children}</QueryClientProviderBase>;
};
