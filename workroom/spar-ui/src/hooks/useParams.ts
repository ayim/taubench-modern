import { useSparUIContext } from '../api/context';
import { SparUIRoutes, LooseRouteParams } from '../api/routes';

export function useParams(route: { strict: false }): LooseRouteParams;
export function useParams<T extends keyof SparUIRoutes>(route: T): SparUIRoutes[T];

export function useParams(route: unknown) {
  const { sparAPIClient } = useSparUIContext();
  return sparAPIClient.useParamsFn(route as never);
}
