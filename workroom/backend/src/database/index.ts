import { Kysely, PostgresDialect } from 'kysely';
import { Pool, type PoolConfig } from 'pg';
import type { Configuration } from '../configuration.js';
import { DatabaseClient, type Database } from './DatabaseClient.js';
import { migrateDatabase } from './migrate.js';
import type { MonitoringContext } from '../monitoring/index.js';

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

const createPool = async ({
  monitoring,
  poolConfig,
}: {
  monitoring: MonitoringContext;
  poolConfig: Pick<PoolConfig, 'database' | 'host' | 'user' | 'password' | 'port' | 'max'>;
}): Promise<Pool> => {
  // Try SSL connection first
  const sslPool = new Pool({
    ...poolConfig,
    ssl: {
      rejectUnauthorized: false,
    },
  });

  try {
    // Test the connection
    const client = await sslPool.connect();
    client.release();

    monitoring.logger.info('Database connection established with SSL');

    return sslPool;
  } catch (error) {
    // Clean up the failed pool
    await sslPool.end();

    if (error instanceof Error && error.message.includes('does not support SSL')) {
      monitoring.logger.info('Database does not support SSL: connecting without');
      const noSslPool = new Pool({
        ...poolConfig,
        ssl: false,
      });

      // Verify the non-SSL connection works
      const client = await noSslPool.connect();
      client.release();
      return noSslPool;
    }

    throw error;
  }
};
