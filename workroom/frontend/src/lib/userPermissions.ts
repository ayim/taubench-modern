export type UserPermission =
  | 'agents.read'
  | 'agents.write'
  | 'documents.read'
  | 'documents.write'
  | 'deployments_monitoring.read'
  | 'users.read'
  | 'users.write';

const defaultPermissions: Record<UserPermission, boolean> = {
  'agents.read': false,
  'agents.write': false,
  'documents.read': false,
  'documents.write': false,
  'deployments_monitoring.read': false,
  'users.read': false,
  'users.write': false,
};

/**
 * Requires to know available permissions beforehand
 * - probably not avoidable if this needs to work in unauthenticated mode?
 */
export const extractUserPermissions = (
  permissions: Array<UserPermission> | undefined,
): Record<UserPermission, boolean> => {
  return (permissions ?? []).reduce<Record<UserPermission, boolean>>(
    (acc, permission) => {
      acc[permission] = true;
      return acc;
    },
    { ...defaultPermissions },
  );
};
