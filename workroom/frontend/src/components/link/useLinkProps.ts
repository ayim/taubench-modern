import { MouseEvent, ReactNode } from 'react';

import type { FileRouteTypes } from '~/routeTree.gen';
import { useNavigate, useParams, useRouter } from '@tanstack/react-router';

type RouteType = FileRouteTypes['to'];

export type LinkProps<T = RouteType> = {
  to: T;
  params?: object;
  children: ReactNode;
  /**
   * If current active page route matches the target link, the subroute will be preserved and appended to the target link
   */
  preserveSubroute?: boolean;
};

export const useLinkProps = <T extends RouteType>(to: T, params: object = {} as object, preserveSubroute = false) => {
  const router = useRouter();
  const currentParams = useParams({ strict: false });
  const currentPathname = router.state.location.pathname;
  const navigate = useNavigate();

  const { href } = router.buildLocation({ to, params: { tenantId: currentParams.tenantId, ...params } as never });
  const current = router.state.matches.some((match) => match.pathname === href);

  let finalHref = href;
  let finalRoute = to;

  if (preserveSubroute) {
    const allParamsPresent = Object.keys(params).every((key) => key in currentParams);

    const targetParams = allParamsPresent ? currentParams : params;
    const { href: currentHref } = router.buildLocation({
      to,
      params: { tenantId: currentParams.tenantId, ...targetParams } as never,
    });

    if (currentPathname.startsWith(currentHref) && currentPathname.length > currentHref.length) {
      const subroute = currentPathname.slice(currentHref.length);

      finalRoute = `${to}${subroute}` as T;
      finalHref = `${href}${subroute}`;
    }
  }

  const onClick = (e: MouseEvent) => {
    e.preventDefault();
    navigate({ to: finalRoute, params: params as never });
  };

  return {
    onClick,
    href: finalHref,
    'aria-current': current ? ('page' as const) : undefined,
  };
};
