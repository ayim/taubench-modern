import type { ApiKeyTable } from './apiKey.js';
import type { SecretDataTable } from './secretData.js';
import type { SessionTable } from './session.js';
import type { UserTable } from './user.js';
import type { UserIdentityTable } from './userIdentity.js';

export interface Database {
  api_key: ApiKeyTable;
  secret_data: SecretDataTable;
  session: SessionTable;
  user: UserTable;
  user_identity: UserIdentityTable;
}
