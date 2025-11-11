import { Kysely } from 'kysely';
import type { Database } from '../types/index.js';

export async function up(db: Kysely<Database>): Promise<void> {
  await db.schema
    .alterTable('user')
    .addColumn('profile_picture_url', 'text', (col) => col.defaultTo(null))
    .execute();
}

export async function down(db: Kysely<Database>): Promise<void> {
  await db.schema.alterTable('user').dropColumn('profile_picture_url').execute();
}
