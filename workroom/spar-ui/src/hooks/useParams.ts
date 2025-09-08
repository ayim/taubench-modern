import { useSparUIContext } from '../api/context';
import { SparUIRoutes } from '../api/routes';

export const useParams = <T extends keyof SparUIRoutes>(route: T) => {
  const { sparAPIClient } = useSparUIContext();
  return sparAPIClient.useParamsFn(route);
};
