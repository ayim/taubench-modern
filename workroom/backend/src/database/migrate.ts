import { promises as fs } from 'node:fs';
import * as path from 'node:path';
import { FileMigrationProvider, Kysely, Migrator } from 'kysely';
import type { Database } from './DatabaseClient.js';
import type { Configuration } from '../configuration.js';
import type { MonitoringContext } from '../monitoring/index.js';

export const migrateDatabase = async ({
  configuration,
  database,
  migrationRecordSchema,
  monitoring,
}: {
  configuration: Configuration;
  database: Kysely<Database>;
  migrationRecordSchema: string;
  monitoring: MonitoringContext;
}): Promise<void> => {
  const migrationDirectory = path.join(import.meta.dirname, 'migrations');

  monitoring.logger.info('Executing migrations', {
    fileName: migrationDirectory,
  });

  const migrator = new Migrator({
    db: database,
    provider: new FileMigrationProvider({
      fs,
      path,
      migrationFolder: migrationDirectory,
    }),
    allowUnorderedMigrations: false,
    migrationLockTableName: configuration.database.migrations.lockTable,
    migrationTableName: configuration.database.migrations.recordsTable,
    migrationTableSchema: migrationRecordSchema,
  });

  const results = await migrator.migrateToLatest();
  for (const result of results.results ?? []) {
    monitoring.logger.info('Migration run', {
      migrationDirection: result.direction,
      migrationName: result.migrationName,
      migrationStatus: result.status,
    });
  }

  if (results.error) {
    monitoring.logger.error(
      'Migrations failed',
      results.error instanceof Error
        ? {
            error: results.error,
          }
        : {
            errorMessage: `${results.error}`,
          },
    );

    throw new Error('Migrations failed to run');
  }
};
