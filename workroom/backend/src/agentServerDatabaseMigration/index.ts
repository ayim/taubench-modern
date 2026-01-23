import type { Result } from '@sema4ai/shared-utils';
import type { Configuration } from '../configuration.js';
import { AgentServerDatabaseClient } from './AgentServerDatabaseClient.js';
import type { DatabaseClient } from '../database/DatabaseClient.js';
import type { UserIdentityType } from '../database/types/userIdentity.js';
import type { MonitoringContext } from '../monitoring/index.js';

export const migrateAgentServerUserSubs = async ({
  agentServerDatabase,
  configuration,
  createUserHandler,
  database,
  identityAuthority,
  identityType,
  monitoring,
}: {
  agentServerDatabase: AgentServerDatabaseClient;
  configuration: Configuration;
  createUserHandler: (opts: {
    agentServerUserIdentityValue: string;
    database: DatabaseClient;
    monitoring: MonitoringContext;
  }) => Promise<Result<{ userId: string }>>;
  database: DatabaseClient;
  identityAuthority: string;
  identityType: UserIdentityType;
  monitoring: MonitoringContext;
}): Promise<void> => {
  const agentServerSubPrefix = `tenant:${configuration.tenant.tenantId}:user:`;

  monitoring.logger.info('Attemping agent server user sync');

  // Get all agent server users
  const agentServerUsersResult = await agentServerDatabase.getAllUsers();
  if (!agentServerUsersResult.success) {
    throw new Error(`Failed to fetch users from agent server database: ${agentServerUsersResult.error.message}`);
  }
  const agentServerUsers = agentServerUsersResult.data;

  if (agentServerUsers.length === 0) {
    monitoring.logger.info('Skipping users migration: No users in agent server database');

    return;
  }

  // Get all SPAR users
  const sparUsersResult = await database.findUserIdentities({
    authority: identityAuthority,
    identityValues: agentServerUsers.map((user) => user.system_identifier),
    type: identityType,
  });
  if (!sparUsersResult.success) {
    throw new Error(`Failed to fetch user identities for agent server users: ${sparUsersResult.error.message}`);
  }
  const sparUsers = sparUsersResult.data;

  const allUserIdsResult = await database.getUserIds();
  if (!allUserIdsResult.success) {
    throw new Error(`Failed to fetch user IDs: ${allUserIdsResult.error.message}`);
  }
  const allUserIds = allUserIdsResult.data;

  // Iterate and update
  for (const agentServerUser of agentServerUsers) {
    if (allUserIds.includes(agentServerUser.system_identifier)) {
      // The user has already been synchronized, so skip
      continue;
    }

    monitoring.logger.info('Synchronizing agent server user', {
      agentServerUserId: agentServerUser.user_id,
      agentServerUserSub: agentServerUser.sub,
    });

    // Ensure a user identity exists
    const sparUserId = await (async () => {
      const sparUserIdentity = sparUsers.find((user) => user.value === agentServerUser.system_identifier);
      if (sparUserIdentity) return sparUserIdentity.user_id;

      const newUserResult = await createUserHandler({
        agentServerUserIdentityValue: agentServerUser.system_identifier,
        database,
        monitoring,
      });
      if (!newUserResult.success) {
        throw new Error(`Failed synchronizing new user from agent server: ${newUserResult.error.message}`);
      }

      return newUserResult.data.userId;
    })();

    // Update user in agent server DB to match the UUID of the actual SPAR user
    const newSub = `${agentServerSubPrefix}${sparUserId}`;

    const updateAgentServerUserResult = await agentServerDatabase.setUserSub({
      sub: newSub,
      userId: agentServerUser.user_id,
    });
    if (!updateAgentServerUserResult.success) {
      throw new Error(`Failed synchronizing user to agent server: ${updateAgentServerUserResult.error.message}`);
    }

    monitoring.logger.info('Synchronized agent server user', {
      agentServerUserId: agentServerUser.user_id,
      agentServerUserSub: newSub,
      userId: sparUserId,
    });
  }
};
