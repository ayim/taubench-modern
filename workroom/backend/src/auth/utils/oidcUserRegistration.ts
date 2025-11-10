import { randomUUID } from 'node:crypto';
import { getNextUserRole } from './userRegistration.js';
import type { DatabaseClient } from '../../database/DatabaseClient.js';
import type { UserRole } from '../../database/types/user.js';
import type { OIDCTokenClaims } from '../../interfaces.js';
import type { MonitoringContext } from '../../monitoring/index.js';
import { type Result } from '../../utils/result.js';

const extractNamesFromClaims = (claims: OIDCTokenClaims): { first: string; last: string } => {
  if (claims.given_name && claims.family_name) {
    return { first: claims.given_name, last: claims.family_name };
  }

  if (claims.name) {
    const match = /^(?<first>[^\s]+)\s*(?<last>.*)$/.exec(claims.name);
    if (match?.groups?.first && match.groups.last) {
      return {
        first: match.groups.first,
        last: match.groups.last,
      };
    }
  }

  return claims.given_name
    ? {
        first: claims.given_name,
        last: claims.family_name ?? '',
      }
    : {
        first: 'User',
        last: 'Unspecified',
      };
};

export const upsertOIDCUser = async ({
  claims,
  database,
  monitoring,
}: {
  claims: OIDCTokenClaims;
  database: DatabaseClient;
  monitoring: MonitoringContext;
}): Promise<
  Result<{
    userId: string;
    userRole: UserRole;
  }>
> => {
  const oidcUserId = claims.sub;
  const names = extractNamesFromClaims(claims);

  monitoring.logger.info('Ingest OIDC user', {
    oidcUserId,
  });

  const existingUserIdentityResult = await database.findUserIdForIdentity({
    authority: claims.iss,
    identityValue: oidcUserId,
    type: 'oidc_sub',
  });
  if (!existingUserIdentityResult.success) {
    return existingUserIdentityResult;
  }

  const existingUserId = existingUserIdentityResult.data;

  if (existingUserId) {
    // Update the names in the parent table
    const updateResult = await database.updateUser({
      user: {
        id: existingUserId,
        first_name: names.first,
        last_name: names.last,
      },
    });
    if (!updateResult.success) {
      return updateResult;
    }

    monitoring.logger.info('OIDC user exists', {
      oidcUserId,
      userId: existingUserId,
    });

    const existingUserResult = await database.getUser({ id: existingUserId });
    if (!existingUserResult.success) {
      return existingUserResult;
    }

    return {
      success: true,
      data: {
        userId: existingUserId,
        userRole: existingUserResult.data.role,
      },
    };
  }

  // We have no matching user identity, so create a new user AND
  // identity at the same time
  const newUserId = randomUUID();

  const nextUserRoleResult = await getNextUserRole({ database });
  if (!nextUserRoleResult.success) {
    return {
      success: false,
      error: {
        code: 'next_user_role_exception',
        message: `Failed to retrieve the next user role: ${nextUserRoleResult.error.message}`,
      },
    };
  }

  monitoring.logger.info('Create new user', {
    oidcUserId,
    userId: newUserId,
    userRole: nextUserRoleResult.data,
  });

  const newUserResult = await database.createUser({
    user: {
      id: newUserId,
      first_name: names.first,
      last_name: names.last,
      role: nextUserRoleResult.data,
    },
  });
  if (!newUserResult.success) {
    return newUserResult;
  }

  const newUserIdentityResult = await database.createUserIdentity({
    userIdentity: {
      user_id: newUserId,
      authority: claims.iss,
      type: 'oidc_sub',
      value: oidcUserId,
    },
  });
  if (!newUserIdentityResult.success) {
    return newUserIdentityResult;
  }

  monitoring.logger.info('Created new user', {
    oidcUserId,
    userId: newUserId,
    userRole: nextUserRoleResult.data,
  });

  return {
    success: true,
    data: {
      userId: newUserId,
      userRole: nextUserRoleResult.data,
    },
  };
};
