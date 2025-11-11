import { TrpcOutput } from './trpc';

export type UserPermission = TrpcOutput['userManagement']['listAvailablePermissions']['permissions'][number];

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
 * @TODO: Use explicit permissions, once we've had time to think on these,
 *  rather than relying on `users.write` to differentiate admins from
 *  regular users.
 */
export const ADMINISTRATION_ACCESS_PERMISSION: UserPermission = 'users.write';

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
