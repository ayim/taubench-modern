import { Kysely, sql } from 'kysely';
import type { Database } from '../types/index.js';

export async function up(db: Kysely<Database>): Promise<void> {
  await db.schema
    .createTable('secret_data')
    .addColumn('id', 'uuid', (col) => col.primaryKey().defaultTo(sql`gen_random_uuid()`))
    .addColumn('master_key_id', 'text', (col) => col.notNull())
    .addColumn('data_key', 'jsonb', (col) => col.notNull())
    .addColumn('encrypted_secret_value', 'jsonb', (col) => col.notNull())
    .addColumn('created_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`NOW()`))
    .addColumn('updated_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`NOW()`))
    .execute();

  await db.schema
    .createTable('api_key')
    .addColumn('id', 'uuid', (col) => col.primaryKey().defaultTo(sql`gen_random_uuid()`))
    .addColumn('name', 'text', (col) => col.notNull())
    .addColumn('secret_data_id', 'uuid', (col) => col.references('secret_data.id').onDelete('cascade').notNull())
    .addColumn('value_hash', 'text', (col) => col.notNull())
    .addColumn('created_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`NOW()`))
    .addColumn('updated_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`NOW()`))
    .execute();

  await db.schema.createIndex('api_key_value_hash_idx').on('api_key').column('value_hash').execute();
}

export async function down(db: Kysely<Database>): Promise<void> {
  await db.schema.dropIndex('api_key_value_hash_idx').ifExists().execute();
  await db.schema.dropTable('api_key').execute();
  await db.schema.dropTable('secret_data').execute();
}
