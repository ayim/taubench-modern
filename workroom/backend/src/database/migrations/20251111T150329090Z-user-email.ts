import { Kysely } from 'kysely';
import type { Database } from '../types/index.js';

export async function up(db: Kysely<Database>): Promise<void> {
  await db.schema
    .alterTable('user_identity')
    .addColumn('email', 'varchar(256)', (col) => col.defaultTo(null))
    .execute();
}

export async function down(db: Kysely<Database>): Promise<void> {
  await db.schema.alterTable('user_identity').dropColumn('email').execute();
}
