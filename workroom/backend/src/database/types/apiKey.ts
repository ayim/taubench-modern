import type { SecretDataReference } from '@sema4ai/secret-management';
import type { ColumnType, Insertable, Selectable, Updateable } from 'kysely';
import type { ResourceTimestampTrait } from './traits.js';

export type ApiKeyTable = {
  id: ColumnType<string, string | undefined, never>;
  last_used_at: ColumnType<Date | null, string | null | undefined, string | null>;
  name: string;
  secret_data_id: SecretDataReference<string>;
  value_hash: string;
} & ResourceTimestampTrait;

export type ApiKey = Selectable<ApiKeyTable>;
export type NewApiKey = Insertable<ApiKeyTable>;
export type ApiKeyUpdate = Updateable<ApiKeyTable>;
