import { MouseEvent, ReactNode } from 'react';

import { useRoute } from '../../hooks';
import type { SparUIRoutes } from '../../api/routes';
import { useSparUIContext } from '../../api/context';
import { NavigationArgs } from '../../api';

export type LinkProps<T = SparUIRoutes> = {
  to: keyof T;
  params: T[keyof T];
  children: ReactNode;
};

export const useLinkProps = <T extends keyof SparUIRoutes>(to: T, params: SparUIRoutes[T]) => {
  const { sparAPIClient } = useSparUIContext();
  const { href, current } = useRoute(to, params);

  const onClick = (e: MouseEvent) => {
    e.preventDefault();
    sparAPIClient.navigate({ to, params } as NavigationArgs);
  };

  return {
    onClick,
    href,
    'aria-current': current ? ('page' as const) : undefined,
  };
};
