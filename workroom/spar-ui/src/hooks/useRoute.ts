import { SparUIRoutes } from '../api/routes';
import { useSparUIContext } from '../api/context';

export const useRoute = <T extends keyof SparUIRoutes>(to: T, params: SparUIRoutes[T]) => {
  const { sparAPIClient } = useSparUIContext();
  return sparAPIClient.useRouteFn(to, params);
};
