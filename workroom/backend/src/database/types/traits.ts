import type { ColumnType } from 'kysely';

export interface ResourceTimestampTrait {
  created_at: ColumnType<Date, never, never>;
  updated_at: ColumnType<Date, never, string>;
}
