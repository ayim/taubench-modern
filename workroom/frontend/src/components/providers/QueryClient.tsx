/* eslint-disable import/no-extraneous-dependencies */
import { FC, ReactNode } from 'react';
import { QueryClient, QueryClientProvider as QueryClientProviderBase } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';

export const queryClient = new QueryClient();

type Props = {
  children?: ReactNode;
};

export const QueryClientProvider: FC<Props> = ({ children }) => {
  return (
    <QueryClientProviderBase client={queryClient}>
      {children}
      <ReactQueryDevtools initialIsOpen={false} client={queryClient} />
    </QueryClientProviderBase>
  );
};
