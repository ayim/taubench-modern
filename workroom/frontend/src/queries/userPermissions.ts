import { useQuery } from '@tanstack/react-query';
import { resolveWorkroomURL } from '~/lib/utils';
import type { UserPermission, UserRole } from '~/lib/userPermissions';

type AuthMeta =
  | { status: 'unauthenticated'; permissions: Array<UserPermission> }
  | { status: 'authenticated'; userId: string; permissions: Array<UserPermission>; userRole: UserRole };

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

export const userPermissionsQueryKey = ['me'];

/**
 * TODO: move to TRPC
 */
export const useUserPermissionsQuery = (options?: { enabled?: boolean }) => {
  return useQuery({
    queryKey: userPermissionsQueryKey,
    queryFn: async (): Promise<{ permissions: Array<UserPermission>; userId?: string; userRole?: UserRole }> => {
      const result = await getAuthMeta();

      if (result?.status === 'authenticated') {
        return { permissions: result.permissions, userId: result.userId, userRole: result.userRole };
      }

      return { permissions: result.permissions };
    },
    ...options,
  });
};
