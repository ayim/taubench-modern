import { randomUUID } from 'node:crypto';
import type { AsyncResult, Result } from '@sema4ai/shared-utils';
import { extractRoleFromOIDCGroupsClaim } from './groupsClaimRole.js';
import { getNextUserRole } from './userRegistration.js';
import type { Configuration } from '../../configuration.js';
import type { DatabaseClient, UpdateUserIdentityPayload, UpdateUserPayload } from '../../database/DatabaseClient.js';
import type { UserRole } from '../../database/types/user.js';
import type { OIDCTokenClaims } from '../../interfaces.js';
import type { MonitoringContext } from '../../monitoring/index.js';
import { isEmail } from '../../utils/parse.js';

export const extractEmailFromClaims = (claims: OIDCTokenClaims): string | null => {
  return [claims.email, claims.sub, claims.preferred_username].find((value) => value && isEmail(value)) ?? null;
};

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

  return claims.given_name || claims.name
    ? {
        first: (claims.given_name || claims.name) as string,
        last: claims.family_name ?? '',
      }
    : {
        first: 'User',
        last: '',
      };
};

export const upsertOIDCUser = async (
  {
    database,
    monitoring,
    configuration,
  }: { database: DatabaseClient; monitoring: MonitoringContext; configuration: Configuration },
  { claims }: { claims: OIDCTokenClaims },
): Promise<
  Result<{
    userId: string;
    userRole: UserRole;
  }>
> => {
  const oidcUserId = claims.sub;
  const names = extractNamesFromClaims(claims);
  const profilePicture = claims.picture ?? null;
  const email = extractEmailFromClaims(claims);
  const roleFromClaims = extractRoleFromOIDCGroupsClaim({ monitoring, configuration }, { claims });

  monitoring.logger.info('Ingest OIDC user', {
    oidcUserId,
  });

  monitoring.logger.debug('Ingesting OIDC user with claims', {
    emailAddress: email ?? undefined,
    oidcClaims: JSON.stringify(claims),
    oidcUserId,
  });

  const existingUserIdentityResult = await database.findUserIdentity({
    authority: claims.iss,
    identityValue: oidcUserId,
    type: 'oidc_sub',
  });
  if (!existingUserIdentityResult.success) {
    return existingUserIdentityResult;
  }

  if (existingUserIdentityResult.data) {
    const existingUserId = existingUserIdentityResult.data.user_id;

    // Update the properties in the parent table
    const updateUserPayload: UpdateUserPayload = {
      id: existingUserId,
      first_name: names.first,
      last_name: names.last,
    };

    if (profilePicture) {
      updateUserPayload.profile_picture_url = profilePicture;
    }

    if (roleFromClaims) {
      updateUserPayload.role = roleFromClaims;
    }

    const updateResult = await database.updateUser({
      user: updateUserPayload,
    });
    if (!updateResult.success) {
      return updateResult;
    }

    monitoring.logger.info('Updating existing OIDC user', {
      oidcUserId,
      userId: existingUserId,
    });

    const existingUserResult = await database.getUser({ id: existingUserId });
    if (!existingUserResult.success) {
      return existingUserResult;
    }

    if (!existingUserIdentityResult.data.email && email) {
      monitoring.logger.debug('Updating user email address', {
        emailAddress: email,
        userId: existingUserIdentityResult.data.user_id,
      });

      // Update the email in the identity table
      const updateIdentityPayload: UpdateUserIdentityPayload = {
        authority: existingUserIdentityResult.data.authority,
        email,
        type: existingUserIdentityResult.data.type,
        user_id: existingUserIdentityResult.data.user_id,
        value: existingUserIdentityResult.data.value,
      };

      const updateIdentityResult = await database.updateUserIdentity({ userIdentity: updateIdentityPayload });
      if (!updateIdentityResult.success) {
        return updateIdentityResult;
      }
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

  const nextUserRoleResult = await (async (): AsyncResult<UserRole> => {
    if (roleFromClaims) {
      return { success: true, data: roleFromClaims };
    }

    const nextUserRoleResult = await getNextUserRole({ database });
    if (!nextUserRoleResult.success) {
      return nextUserRoleResult;
    }

    return { success: true, data: nextUserRoleResult.data };
  })();

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
      profile_picture_url: profilePicture,
    },
  });
  if (!newUserResult.success) {
    return newUserResult;
  }

  const newUserIdentityResult = await database.createUserIdentity({
    userIdentity: {
      email,
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
