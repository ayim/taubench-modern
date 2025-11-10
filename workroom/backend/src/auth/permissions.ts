import type { WorkRoomV1 } from '@sema4ai/robocloud-sign-interface';
import type { UserRole } from '../database/types/user.js';

export type Permission = WorkRoomV1['capabilities']['byTenantId'][string][number] | 'users.read' | 'users.write';

export type Role = {
  id: UserRole;
  name: string;
  permissions: Array<Permission>;
};

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

const operator: Readonly<Role> = {
  id: 'operator',
  name: 'Operator',
  permissions: ['agents.read', 'agents.write', 'deployments_monitoring.read'],
};

const knowledgeWorker: Readonly<Role> = {
  id: 'knowledgeWorker',
  name: 'Knowledge Worker',
  permissions: ['agents.read', 'agents.write'],
};

const agentSupervisor: Readonly<Role> = {
  id: 'agentSupervisor',
  name: 'Agent Supervisor',
  permissions: ['agents.read', 'agents.write', 'documents.read', 'documents.write'],
};

type RoleRecord = Readonly<Record<Role['id'], Role>>;
export const Roles: RoleRecord = {
  admin,
  operator,
  knowledgeWorker,
  agentSupervisor,
};

export const RoleIDs = Object.keys(Roles) as Array<UserRole>;
