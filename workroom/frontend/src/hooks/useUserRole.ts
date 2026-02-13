import { useMemo } from 'react';
import { ADMINISTRATION_ACCESS_PERMISSION } from '~/lib/userPermissions';
import { useUserPermissionsQuery } from '~/queries/userPermissions';

export enum UserRole {
  Admin = 'admin',
}

export const useUserRole = (role: UserRole) => {
  const { data: userPermissions } = useUserPermissionsQuery();

  const hasRole = useMemo(() => {
    switch (role) {
      case UserRole.Admin:
        return (
          userPermissions?.userRole === 'admin' ||
          userPermissions?.permissions.includes(ADMINISTRATION_ACCESS_PERMISSION)
        );
      default:
        return false;
    }
  }, [userPermissions]);

  return hasRole;
};
