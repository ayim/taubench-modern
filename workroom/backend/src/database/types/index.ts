import type { SessionTable } from './session.js';
import type { UserTable } from './user.js';
import type { UserIdentityTable } from './userIdentity.js';

export interface Database {
  session: SessionTable;
  user: UserTable;
  user_identity: UserIdentityTable;
}
