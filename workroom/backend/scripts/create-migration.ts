import { writeFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { createInterface as createReadlineInterface } from 'node:readline/promises';

const MIGRATION_TEMPLATE = `import { Kysely } from 'kysely';
import type { Database } from '../DatabaseClient.js';

export async function up(db: Kysely<Database>): Promise<void> {
  // Migration code
}

export async function down(db: Kysely<Database>): Promise<void> {
  // Migration code
}
`;

(async () => {
  const migrationsPath = resolve(import.meta.dirname, '../src/database/migrations');

  const timestamp = new Date().toISOString().replace(/[^0-9A-Z]+/g, '');

  const rl = createReadlineInterface({
    input: process.stdin,
    output: process.stdout,
  });
  const rawName = await rl.question('Migration name: ');
  rl.close();
  const migrationName = rawName
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9-]/gi, '-')
    .replace(/^-+/, '')
    .replace(/-+$/, '');

  if (migrationName.length === 0) {
    throw new Error('Invalid migration name');
  }

  const migrationPath = join(migrationsPath, `${timestamp}-${migrationName}.ts`);

  await writeFile(migrationPath, MIGRATION_TEMPLATE);

  // eslint-disable-next-line no-console
  console.log(`Migration written:\n\t${migrationPath}`);
})().catch((err) => {
  // eslint-disable-next-line no-console
  console.error(err);
  process.exit(1);
});
