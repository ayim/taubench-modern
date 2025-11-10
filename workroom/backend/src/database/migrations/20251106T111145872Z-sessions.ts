import { Kysely, sql } from 'kysely';
import type { Database } from '../types/index.js';

export async function up(db: Kysely<Database>): Promise<void> {
  await db.schema
    .createTable('session')
    .addColumn('id', 'uuid', (col) => col.primaryKey())
    .addColumn('data', 'jsonb', (col) => col.notNull())
    .addColumn('expires', 'timestamptz', (col) => col.notNull())
    .addColumn('created_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`NOW()`))
    .addColumn('updated_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`NOW()`))
    .execute();
}

export async function down(db: Kysely<Database>): Promise<void> {
  await db.schema.dropTable('session').execute();
}
