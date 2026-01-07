import type { DataKeyEncryptedPayload, SecretEncryptedPayload } from '@sema4ai/secret-management';
import type { ColumnType, Insertable, Selectable, Updateable } from 'kysely';
import type { ResourceTimestampTrait } from './traits.js';

export type SecretDataTable = {
  id: ColumnType<string, string | undefined, never>;
  master_key_id: string;
  data_key: ColumnType<DataKeyEncryptedPayload, string, string>;
  encrypted_secret_value: ColumnType<SecretEncryptedPayload, string, string>;
} & ResourceTimestampTrait;

export type SecretData = Selectable<SecretDataTable>;
export type NewSecretData = Insertable<SecretDataTable>;
export type SecretDataUpdate = Updateable<SecretDataTable>;
