import { Kysely, PostgresDialect } from 'kysely';
import type { Configuration } from '../configuration.js';
import { DatabaseClient } from './DatabaseClient.js';
import { createPool } from './helpers.js';
import { migrateDatabase } from './migrate.js';
import type { MonitoringContext } from '../monitoring/index.js';
import type { Database } from './types/index.js';

export const createDatabaseClient = async ({
  configuration,
  monitoring,
}: {
  configuration: Configuration;
  monitoring: MonitoringContext;
}): Promise<DatabaseClient> => {
  monitoring.logger.debug('Configure database', {
    dbHost: configuration.database.host,
    dbName: configuration.database.name,
    dbPort: configuration.database.port,
    dbSchema: configuration.database.schema,
  });

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

  const database = new Kysely<Database>({
    dialect,
  }).withSchema(configuration.database.schema);

  await migrateDatabase({
    configuration,
    database,
    migrationRecordSchema: configuration.database.schema,
    monitoring,
  });

  return new DatabaseClient({
    database,
    monitoring,
  });
};
