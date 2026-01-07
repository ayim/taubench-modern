import type { Kysely } from 'kysely';
import type { Database } from '../types/index.js';

export const up = async (db: Kysely<Database>): Promise<void> => {
  await db.schema.alterTable('api_key').addColumn('last_used_at', 'timestamptz').execute();
};

export const down = async (db: Kysely<Database>): Promise<void> => {
  await db.schema.alterTable('api_key').dropColumn('last_used_at').execute();
};
