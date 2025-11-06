import { useQuery } from '@tanstack/react-query';
import { resolveWorkroomURL } from '~/lib/utils';
import type { UserPermission } from '~/lib/userPermissions';

type AuthMeta =
  | { status: 'unauthenticated' }
  | { status: 'authenticated'; userId: string; permissions: Array<UserPermission> };

let __metaPromise: Promise<AuthMeta> | null = null;

const getAuthMeta = async (): Promise<AuthMeta> => {
  if (__metaPromise) {
    return __metaPromise;
  }

  __metaPromise = (async () => {
    const url = resolveWorkroomURL('/auth/meta');
    const response = await fetch(url, {
      method: 'GET',
    }).then(async (res) => await res.json());

    __metaPromise = null;

    return response as AuthMeta;
  })();

  return __metaPromise;
};

export const useUserPermissionsQuery = () => {
  return useQuery({
    queryKey: ['me'],
    queryFn: async (): Promise<Array<UserPermission>> => {
      const result = await getAuthMeta();

      if (result?.status === 'authenticated') {
        return result.permissions;
      }

      return [];
    },
  });
};
