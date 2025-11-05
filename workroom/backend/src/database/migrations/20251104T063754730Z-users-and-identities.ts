import { Kysely, sql } from 'kysely';
import type { Database } from '../DatabaseClient.js';

export async function up(db: Kysely<Database>): Promise<void> {
  await db.schema
    .createTable('user')
    .addColumn('id', 'uuid', (col) => col.primaryKey())
    .addColumn('first_name', 'text', (col) => col.notNull())
    .addColumn('last_name', 'text', (col) => col.notNull())
    .addColumn('role', 'varchar(64)', (col) => col.notNull())
    .addColumn('created_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`NOW()`))
    .addColumn('updated_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`NOW()`))
    .execute();

  await db.schema
    .createTable('user_identity')
    .addColumn('user_id', 'uuid', (col) => col.references('user.id').onDelete('cascade'))
    .addColumn('type', 'varchar(64)', (col) => col.notNull())
    .addColumn('authority', 'varchar(256)', (col) => col.notNull())
    .addColumn('value', 'text', (col) => col.notNull())
    .addColumn('created_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`NOW()`))
    .addColumn('updated_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`NOW()`))
    .execute();

  await db.schema.createIndex('user_identity_user_id_idx').on('user_identity').column('user_id').execute();
}

export async function down(db: Kysely<Database>): Promise<void> {
  await db.schema.dropIndex('user_identity_user_id_idx').ifExists().execute();
  await db.schema.dropTable('user_identity').execute();
  await db.schema.dropTable('user').execute();
}
