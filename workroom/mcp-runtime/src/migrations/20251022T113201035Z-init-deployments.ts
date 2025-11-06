import { Kysely, sql } from 'kysely';

export async function up(db: Kysely<any>): Promise<void> {
  await db.schema
    .createTable('deployment')
    .addColumn('id', 'uuid', (col) => col.primaryKey())
    .addColumn('created_at', 'timestamptz', (col) => col.defaultTo(sql`NOW()`).notNull())
    .addColumn('status', 'text', (col) => col.notNull().defaultTo('created'))
    .addColumn('port', 'integer', (col) => col.unique())
    .addColumn('zip_path', 'text')
    .execute();
}

export async function down(db: Kysely<any>): Promise<void> {
  await db.schema.dropTable('deployment').execute();
}
