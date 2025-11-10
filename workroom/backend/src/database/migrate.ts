import { promises as fs } from 'node:fs';
import * as path from 'node:path';
import { pathToFileURL } from 'node:url';
import type { Migration, MigrationProvider } from 'kysely';
import { Kysely, Migrator } from 'kysely';
import type { Configuration } from '../configuration.js';
import type { MonitoringContext } from '../monitoring/index.js';
import type { Database } from './types/index.js';

/**
 * A custom, cross-platform compatible file migrator for Kysely.
 * Needed as we run migrations via files on all OSes, and Windows
 * has some issues with the built in one (re pathing).
 * @see {@link https://github.com/kysely-org/kysely/issues/254} GitHub issue
 */
class CrossPlatformFileMigrationProvider implements MigrationProvider {
  constructor(
    private readonly params: {
      fs: typeof fs;
      path: typeof path;
      migrationFolder: string;
    },
  ) {}

  async getMigrations(): Promise<Record<string, Migration>> {
    const migrations: Record<string, Migration> = {};
    const files = await this.params.fs.readdir(this.params.migrationFolder);

    for (const fileName of files) {
      if (fileName.endsWith('.d.ts')) {
        continue;
      }

      if (fileName.endsWith('.js') || fileName.endsWith('.ts')) {
        const migrationFilePath = this.params.path.join(this.params.migrationFolder, fileName);
        const migrationFileUrl = pathToFileURL(migrationFilePath).href;
        const migration = await import(migrationFileUrl);
        const migrationKey = fileName.substring(0, fileName.lastIndexOf('.'));

        migrations[migrationKey] = migration;
      }
    }

    return migrations;
  }
}

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
    provider: new CrossPlatformFileMigrationProvider({
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
