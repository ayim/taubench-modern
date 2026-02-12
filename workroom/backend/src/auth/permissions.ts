import type { UserRole } from '../database/types/user.js';
import { exhaustiveUnionArray } from '../utils/types.js';

export type Permission =
  | 'agents.read'
  | 'agents.write'
  | 'deployments_monitoring.read'
  | 'documents.read'
  | 'documents.write'
  | 'users.read'
  | 'users.write';

export type Role = {
  id: UserRole;
  name: string;
  permissions: Array<Permission>;
};

export const AllPermissions = exhaustiveUnionArray<Permission>()([
  'agents.read',
  'agents.write',
  'documents.read',
  'documents.write',
  'deployments_monitoring.read',
  'users.read',
  'users.write',
] as const);

const admin: Readonly<Role> = {
  id: 'admin',
  name: 'Admin',
  permissions: [
    'agents.read',
    'agents.write',
    'deployments_monitoring.read',
    'documents.read',
    'documents.write',
    'users.read',
    'users.write',
  ],
};

const knowledgeWorker: Readonly<Role> = {
  id: 'knowledgeWorker',
  name: 'Knowledge Worker',
  permissions: ['agents.read', 'agents.write'],
};

type RoleRecord = Readonly<Record<Role['id'], Role>>;
export const Roles: RoleRecord = {
  admin,
  knowledgeWorker,
};

export const RoleIDs = Object.keys(Roles) as Array<UserRole>;
