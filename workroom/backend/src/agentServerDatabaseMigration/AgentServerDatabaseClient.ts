import { Kysely, PostgresDialect } from 'kysely';
import type { Configuration } from '../configuration.js';
import type { AgentServerDatabase } from './types.js';
import { createPool } from '../database/helpers.js';
import type { MonitoringContext } from '../monitoring/index.js';
import { asResult, type Result } from '../utils/result.js';

const NOOP = () => {};

export class AgentServerDatabaseClient {
  private agentServerSubPrefix: string;
  private database: Kysely<AgentServerDatabase>;

  constructor({ configuration, database }: { configuration: Configuration; database: Kysely<AgentServerDatabase> }) {
    this.database = database;
    this.agentServerSubPrefix = `tenant:${configuration.tenant.tenantId}:user:`;
  }

  async getAllUsers(): Promise<
    Result<
      Array<{
        system_identifier: string;
        sub: string;
        user_id: string;
      }>
    >
  > {
    return asResult(() =>
      this.database
        .selectFrom('user')
        .select('sub')
        .select('user_id')
        .where('sub', 'like', `${this.agentServerSubPrefix}%`)
        .execute()
        .then((users) =>
          users.map((user) => ({
            ...user,
            system_identifier: user.sub.substring(this.agentServerSubPrefix.length),
          })),
        ),
    );
  }

  async setUserSub({ sub, userId }: { sub: string; userId: string }): Promise<Result<void>> {
    return asResult(() =>
      this.database.updateTable('user').set('sub', sub).where('user_id', '=', userId).execute().then(NOOP),
    );
  }
}

export const createAgentServerDatabaseClient = async ({
  configuration,
  monitoring,
}: {
  configuration: Configuration;
  monitoring: MonitoringContext;
}): Promise<AgentServerDatabaseClient> => {
  const pool = await createPool({
    monitoring,
    poolConfig: {
      database: configuration.database.name,
      host: configuration.database.host,
      user: configuration.database.username,
      password: configuration.database.password,
      port: configuration.database.port,
      max: configuration.database.pool.max,
    },
  });

  const dialect = new PostgresDialect({
    pool,
  });

  const database = new Kysely<AgentServerDatabase>({
    dialect,
  }).withSchema(configuration.database.agentServerSchema);

  return new AgentServerDatabaseClient({ configuration, database });
};
