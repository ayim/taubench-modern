import { createTRPCQueryUtils, httpBatchLink } from '@trpc/react-query';
import { useState } from 'react';
import type { SPARRouter } from '@spar-service';
import { trpc } from '~/lib/trpc';
import { RouterProvider } from './providers/Router';
import { queryClient } from './providers/QueryClient';

export const TRPCProvider = ({ trpcUrl }: { trpcUrl: string }) => {
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
