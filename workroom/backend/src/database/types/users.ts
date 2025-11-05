import type { Insertable, Selectable, Updateable } from 'kysely';
import type { ResourceTimestampTrait } from './traits.js';

export type UserRole = 'admin' | 'operator' | 'knowledgeWorker' | 'agentSupervisor';

export type UserTable = {
  id: string;
  first_name: string;
  last_name: string;
  role: UserRole;
} & ResourceTimestampTrait;

export type User = Selectable<UserTable>;
export type NewUser = Insertable<UserTable>;
export type UserUpdate = Updateable<UserTable>;
