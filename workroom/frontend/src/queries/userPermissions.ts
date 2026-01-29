import { useQuery } from '@tanstack/react-query';
import { resolveWorkroomURL } from '~/lib/utils';
import type { UserPermission, UserRole } from '~/lib/userPermissions';

type AuthMeta =
  | { status: 'unauthenticated'; permissions: Array<UserPermission> }
  | { status: 'authenticated'; userId: string; permissions: Array<UserPermission>; userRole: UserRole };

let metaPromise: Promise<AuthMeta> | null = null;

const getAuthMeta = async (): Promise<AuthMeta> => {
  if (metaPromise) {
    return metaPromise;
  }

  metaPromise = (async () => {
    const url = resolveWorkroomURL('/auth/meta');
    const response = await fetch(url, {
      method: 'GET',
    }).then(async (res) => res.json());

    metaPromise = null;

    return response as AuthMeta;
  })();

  return metaPromise;
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
