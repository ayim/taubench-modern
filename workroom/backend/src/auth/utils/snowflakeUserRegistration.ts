import { randomUUID } from 'node:crypto';
import { getNextUserRole } from './userRegistration.js';
import type { DatabaseClient, UpdateUserIdentityPayload, UpdateUserPayload } from '../../database/DatabaseClient.js';
import type { UserRole } from '../../database/types/user.js';
import type { MonitoringContext } from '../../monitoring/index.js';
import { isEmail } from '../../utils/parse.js';
import type { Result } from '../../utils/result.js';
import { SNOWFLAKE_AUTHORITY } from '../../utils/snowflake.js';

export const upsertSnowflakeUser = async ({
  database,
  monitoring,
  snowflake,
}: {
  database: DatabaseClient;
  monitoring: MonitoringContext;
  snowflake: {
    currentUserContextHeader: string;
  };
}): Promise<
  Result<{
    userId: string;
    userRole: UserRole;
  }>
> => {
  const snowflakeUserId = snowflake.currentUserContextHeader;
  const email = isEmail(snowflake.currentUserContextHeader) ? snowflake.currentUserContextHeader : null;
  const names: { first: string; last: string } = {
    first: 'User',
    last: '',
  };

  monitoring.logger.info('Ingest Snowflake user', {
    snowflakeUserId,
  });

  monitoring.logger.debug('Ingesting Snowflake user with claims', {
    emailAddress: email ?? undefined,
    snowflakeUserId,
  });

  const existingUserIdentityResult = await database.findUserIdentity({
    authority: SNOWFLAKE_AUTHORITY,
    identityValue: snowflakeUserId,
    type: 'snowflake_user_header',
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

    const updateResult = await database.updateUser({
      user: updateUserPayload,
    });
    if (!updateResult.success) {
      return updateResult;
    }

    monitoring.logger.info('Updating existing Snowflake user', {
      snowflakeUserId,
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
    snowflakeUserId,
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
      email,
      user_id: newUserId,
      authority: SNOWFLAKE_AUTHORITY,
      type: 'snowflake_user_header',
      value: snowflakeUserId,
    },
  });
  if (!newUserIdentityResult.success) {
    return newUserIdentityResult;
  }

  monitoring.logger.info('Created new user', {
    snowflakeUserId,
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
