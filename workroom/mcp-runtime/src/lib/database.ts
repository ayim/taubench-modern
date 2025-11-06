import { asResult, type AsyncResult } from '@sema4ai/robocloud-shared-utils';
import { promises as fs } from 'fs';
import { FileMigrationProvider, Kysely, Migrator, PostgresDialect } from 'kysely';
import * as path from 'path';
import { Pool } from 'pg';
import z from 'zod';
import type { Database, Deployment, DeploymentUpdate } from '../types.ts';
import type { Configuration } from '../configuration.ts';

export const DeploymentStatus = z.enum(['created', 'building', 'running', 'build_failed']);

export type DatabaseClient = {
  createDeployment: ({ id, port }: Pick<Deployment, 'id' | 'port'>) => AsyncResult<Deployment>;
  getDeployment: ({ id }: Pick<Deployment, 'id'>) => AsyncResult<Deployment | null>;
  listDeployments: () => AsyncResult<Deployment[]>;
  updateDeployment: (deployment: DeploymentUpdate & { id: string }) => AsyncResult<Deployment>;
  deleteDeployment: ({ id }: Pick<Deployment, 'id'>) => AsyncResult<{ id: string }>;
  getAvailablePort: () => AsyncResult<number | null>;

  shutdown: () => Promise<void>;
};

const getDatabaseClient = ({
  kysely: db,
  configuration,
}: {
  kysely: Kysely<Database>;
  configuration: Pick<Configuration, 'maxServerCount' | 'minServerPort'>;
}): DatabaseClient => ({
  createDeployment: async ({ id, port }) => {
    return asResult(() =>
      db //
        .insertInto('deployment')
        .values({ id, port })
        .returningAll()
        .executeTakeFirstOrThrow(),
    );
  },

  getDeployment: ({ id }) => {
    return asResult(() =>
      db //
        .selectFrom('deployment')
        .selectAll()
        .where('id', '=', id)
        .executeTakeFirstOrThrow(),
    );
  },

  listDeployments: () => {
    return asResult(() =>
      db //
        .selectFrom('deployment')
        .selectAll()
        .execute(),
    );
  },

  updateDeployment: (deployment) => {
    return asResult(() =>
      db
        .updateTable('deployment')
        .set({
          status: deployment.status,
          port: deployment.port,
          zip_path: deployment.zip_path,
        })
        .where('id', '=', deployment.id)
        .returningAll()
        .executeTakeFirstOrThrow(),
    );
  },

  deleteDeployment: async ({ id }) => {
    const result = await asResult(() =>
      db //
        .deleteFrom('deployment')
        .where('id', '=', id)
        .execute(),
    );
    if (!result.success) {
      return result;
    }
    return {
      success: true,
      data: { id },
    };
  },

  getAvailablePort: async () => {
    const allAssignablePorts = Array.from(
      { length: configuration.maxServerCount },
      (_, i) => configuration.minServerPort + i,
    );
    const result = await asResult(() =>
      db //
        .selectFrom('deployment')
        .select('port')
        .execute(),
    );
    if (!result.success) {
      return result;
    }
    const takenPorts = result.data.map(({ port }) => port);
    const availablePort = allAssignablePorts.find((port) => !takenPorts.includes(port)) ?? null;
    return {
      success: true,
      data: availablePort,
    };
  },

  shutdown: async () => {
    await db.destroy();
  },
});

export const runMigrationsAndGetDatabaseClient = async (
  configuration: Pick<Configuration, 'database' | 'maxServerCount' | 'minServerPort'>,
) => {
  const dialect = new PostgresDialect({
    pool: new Pool(configuration.database.poolConfiguration),
  });
  const kysely = new Kysely<Database>({ dialect }).withSchema(configuration.database.schema);
  const migrator = new Migrator({
    db: kysely,
    allowUnorderedMigrations: false,
    migrationLockTableName: configuration.database.migrations.lockTable,
    migrationTableName: configuration.database.migrations.recordsTable,
    migrationTableSchema: configuration.database.schema,
    provider: new FileMigrationProvider({
      fs,
      path,
      migrationFolder: path.join(import.meta.dirname, 'migrations'),
    }),
  });

  const { error, results } = await migrator.migrateToLatest();

  for (const migrationResult of results ?? []) {
    if (migrationResult.status === 'Success') {
      console.log(`Migration "${migrationResult.migrationName}" was executed successfully`);
    } else if (migrationResult.status === 'Error') {
      console.error(`Failed to execute migration "${migrationResult.migrationName}"`);
    }
  }

  if (error) {
    console.error('Failed to migrate');
    console.error(error);
    process.exit(1);
  }

  return getDatabaseClient({ kysely, configuration });
};
