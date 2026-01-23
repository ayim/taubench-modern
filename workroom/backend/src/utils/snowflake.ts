import { asError } from '@sema4ai/shared-utils';
import { backOff } from 'exponential-backoff';
import type { AgentServerDatabaseClient } from '../agentServerDatabaseMigration/AgentServerDatabaseClient.js';
import { migrateAgentServerUserSubs } from '../agentServerDatabaseMigration/index.js';
import { upsertSnowflakeUser } from '../auth/utils/snowflakeUserRegistration.js';
import type { Configuration } from '../configuration.js';
import type { DatabaseClient } from '../database/DatabaseClient.js';
import type { MonitoringContext } from '../monitoring/index.js';

/**
 * Snowflake user identity header
 * @example
 *  "perry@sema4.ai"
 * @example
 *  "perry"
 */
export const SNOWFLAKE_AUTH_HEADER = 'sf-context-current-user';

/**
 * Static value to use for authority "issuer" when handling Snowflake
 * user identities in the database. Do not change - previous sessions
 * and identities will disconnect.
 */
export const SNOWFLAKE_AUTHORITY = 'https://app.snowflake.com';

export const migrateAgentServerUsersForSPCS = async ({
  agentServerDatabase,
  configuration,
  database,
  monitoring,
}: {
  agentServerDatabase: AgentServerDatabaseClient;
  configuration: Configuration;
  database: DatabaseClient;
  monitoring: MonitoringContext;
}) => {
  // Wait for database to become ready
  const startTime = Date.now();
  let attempts = 0;
  try {
    await backOff(
      async () => {
        monitoring.logger.info('Checking if agent server database is ready for user migration', {
          count: ++attempts,
        });

        const databaseReadyResult = await agentServerDatabase.userTableMigratedAndReady();

        if (!databaseReadyResult.success) {
          throw new Error(`Agent server database ready check failed: ${databaseReadyResult.error.message}`);
        }

        if (!databaseReadyResult.data) {
          throw new Error('Agent server database not yet ready');
        }

        monitoring.logger.info('Agent server database ready for user migration');
      },
      {
        jitter: 'none',
        maxDelay: 5000,
        numOfAttempts: 15,
        startingDelay: 150,
      },
    );
  } catch (err) {
    const error = asError(err);
    const duration = Date.now() - startTime;

    monitoring.logger.error('Agent server database did not become ready', {
      count: attempts,
      duration,
    });

    if (/not yet ready/i.test(error.message)) {
      throw new Error(
        `Failed performing users migration: Agent server database did not become ready in ${Math.ceil(duration / 1000)} seconds`,
      );
    }

    throw error;
  }

  // Perform migration
  await migrateAgentServerUserSubs({
    agentServerDatabase,
    configuration,
    createUserHandler: async ({ agentServerUserIdentityValue, database, monitoring }) =>
      upsertSnowflakeUser({
        database,
        monitoring,
        snowflake: {
          currentUserContextHeader: agentServerUserIdentityValue,
        },
      }),
    database,
    identityAuthority: SNOWFLAKE_AUTHORITY,
    identityType: 'snowflake_user_header',
    monitoring,
  });
};
