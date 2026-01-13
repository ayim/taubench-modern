import { MouseEvent, ReactNode } from 'react';

import { useRoute } from '../../hooks';
import type { SparUIRoutes } from '../../api/routes';
import { useSparUIContext } from '../../api/context';
import { NavigationArgs } from '../../api';

export type LinkProps<T = SparUIRoutes> = {
  to: keyof T;
  params: T[keyof T];
  children: ReactNode;
  /**
   * If current active page route matches the target link, the subroute will be preserved and appended to the target link
   */
  preserveSubroute?: boolean;
};

export const useLinkProps = <T extends keyof SparUIRoutes>(
  to: T,
  params: SparUIRoutes[T],
  preserveSubroute = false,
) => {
  const { sparAPIClient } = useSparUIContext();
  const { href, current } = useRoute(to, params);
  const currentPathname = sparAPIClient.usePathnameFn();

  let finalHref = href;
  let finalRoute = to;

  if (preserveSubroute) {
    const currentParams = sparAPIClient.useParamsFn(to);
    const allParamsPresent = Object.keys(params).every((key) => key in currentParams);
    const { href: currentHref } = sparAPIClient.useRouteFn(to, allParamsPresent ? currentParams : params);

    if (currentPathname.startsWith(currentHref) && currentPathname.length > currentHref.length) {
      const subroute = currentPathname.slice(currentHref.length);

      finalRoute = `${to}${subroute}` as T;
      finalHref = `${href}${subroute}`;
    }
  }

  const onClick = (e: MouseEvent) => {
    e.preventDefault();
    sparAPIClient.navigate({ to: finalRoute, params } as NavigationArgs);
  };

  return {
    onClick,
    href: finalHref,
    'aria-current': current ? ('page' as const) : undefined,
  };
};
