import { useQuery } from '@tanstack/react-query';

import { getAuthOptions } from '~/config/auth';

export const useAuthOptions = () => {
  return useQuery({
    queryKey: ['authOptions'],
    queryFn: getAuthOptions,
  });
};
