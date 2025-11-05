import type { WorkRoomV1 } from '@sema4ai/robocloud-sign-interface';
import type { UserRole } from '../database/types/users.js';

export type Permission = WorkRoomV1['capabilities']['byTenantId'][string][number] | 'users.read' | 'users.write';

export type Role = {
  id: UserRole;
  permissions: Array<Permission>;
};

const admin: Readonly<Role> = {
  id: 'admin',
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

const operator: Readonly<Role> = {
  id: 'operator',
  permissions: ['agents.read', 'agents.write', 'deployments_monitoring.read'],
};

const knowledgeWorker: Readonly<Role> = {
  id: 'knowledgeWorker',
  permissions: ['agents.read', 'agents.write'],
};

const agentSupervisor: Readonly<Role> = {
  id: 'agentSupervisor',
  permissions: ['agents.read', 'agents.write', 'documents.read', 'documents.write'],
};

type RoleRecord = Readonly<Record<Role['id'], Role>>;
export const Roles: RoleRecord = {
  admin,
  operator,
  knowledgeWorker,
  agentSupervisor,
};

export const RoleNames = Object.keys(Roles) as Array<UserRole>;
