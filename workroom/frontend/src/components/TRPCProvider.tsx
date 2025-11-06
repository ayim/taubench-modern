import { createTRPCQueryUtils, httpBatchLink } from '@trpc/react-query';
import { useMemo, useState } from 'react';
import { QueryClient } from '@tanstack/react-query';
import type { SPARRouter } from '@spar-service';
import { trpc } from '~/lib/trpc';
import { RouterProvider } from './providers/Router';

export const TRPCProvider = ({ trpcUrl }: { trpcUrl: string }) => {
  const queryClient = useMemo(() => new QueryClient(), []);

  const [trpcClient] = useState(() => {
    const client = trpc.createClient({
      links: [
        httpBatchLink({
          url: trpcUrl,
        }),
      ],
    });

    const utils = createTRPCQueryUtils<SPARRouter>({
      queryClient,
      client,
    });

    return { client, utils };
  });

  return (
    <trpc.Provider client={trpcClient.client} queryClient={queryClient}>
      <RouterProvider trpcUtils={trpcClient.utils} />
    </trpc.Provider>
  );
};
