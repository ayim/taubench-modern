import type { Configuration } from '../../configuration.js';
import type { UserRole } from '../../database/types/user.js';
import type { OIDCTokenClaims } from '../../interfaces.js';
import type { MonitoringContext } from '../../monitoring/index.js';

const VALID_ROLES: ReadonlyArray<UserRole> = ['admin', 'knowledgeWorker'];

// CURRENT: expected values for groups are "admin" | "knowledgeWorker"
// FUTURE: an SSO management view should allow mapping arbitrary group names to SPAR roles

export const extractRoleFromOIDCGroupsClaim = (
  { monitoring, configuration }: { monitoring: MonitoringContext; configuration: Pick<Configuration, 'auth'> },
  { claims }: { claims: OIDCTokenClaims },
): UserRole | null => {
  if (configuration.auth.type !== 'oidc') {
    return null;
  }

  const { oidcGroupsClaim } = configuration.auth;
  const claimValue = claims[oidcGroupsClaim];

  if (claimValue === undefined || claimValue === null) {
    monitoring.logger.debug('No groups claim found in OIDC token', {
      oidcGroupsClaimName: oidcGroupsClaim,
    });
    return null;
  }

  if (!Array.isArray(claimValue)) {
    monitoring.logger.info('Groups claim has unexpected type', {
      oidcGroupsClaimName: oidcGroupsClaim,
      oidcGroupsClaimType: typeof claimValue,
    });
    return null;
  }

  const matchedRoles = claimValue.filter((group): group is UserRole => VALID_ROLES.includes(group as UserRole));

  const droppedGroups = claimValue.filter((group) => !VALID_ROLES.includes(group as UserRole));
  if (droppedGroups.length > 0) {
    monitoring.logger.info('Dropped non-matching groups from OIDC claim', {
      oidcDroppedGroups: droppedGroups.join(', '),
      oidcExpectedRoles: VALID_ROLES.join(', '),
      oidcGroupsClaimName: oidcGroupsClaim,
      oidcReceivedGroups: claimValue.join(', '),
    });
  }

  if (matchedRoles.length === 0) {
    return null;
  }

  return matchedRoles.includes('admin') ? 'admin' : matchedRoles[0];
};
