import type { ColumnType, Insertable, Selectable, Updateable } from 'kysely';

export interface Database {
  deployment: DeploymentTable;
}

type DeploymentStatus = 'created' | 'building' | 'running' | 'build_failed';
export interface DeploymentTable {
  id: string;
  created_at: ColumnType<Date, string | undefined, never>;
  status: ColumnType<DeploymentStatus, DeploymentStatus | undefined>;
  port: number | null;
  zip_path: string | null;
}

export type Deployment = Selectable<DeploymentTable>;
export type NewDeployment = Insertable<DeploymentTable>;
export type DeploymentUpdate = Updateable<DeploymentTable>;
