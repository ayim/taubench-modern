import type { Insertable, Selectable, Updateable } from 'kysely';
import type { ResourceTimestampTrait } from './traits.js';
import type { UserTable } from './user.js';

export type UserIdentityType = 'oidc_sub';

export type UserIdentityTable = {
  user_id: UserTable['id'];
  type: UserIdentityType;
  /**
   * The authority providing this user identity. In the case of OIDC,
   * this would be the issuer.
   */
  authority: string;
  /**
   * The identity value - a user ID, email, or whatever is provided
   * in an OIDC `sub` field, for instance. This value
   */
  value: string;
  /**
   * User email address associated with this provider, if available
   */
  email: string | null;
} & ResourceTimestampTrait;

export type UserIdentity = Selectable<UserIdentityTable>;
export type NewUserIdentity = Insertable<UserIdentityTable>;
export type UserIdentityUpdate = Updateable<UserIdentityTable>;
