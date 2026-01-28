import { components as workroomComponents } from '@sema4ai/workroom-interface';

import { createSparQueryOptions } from './shared';
type AuditLog = workroomComponents['schemas']['AuditLog'];

export const getListAuditLogsQueryKey = () => ['auditLogs'];

export const getListAuditLogsQueryOptions = createSparQueryOptions()(({ agentAPIClient }) => ({
  queryKey: getListAuditLogsQueryKey(),
  queryFn: async (): Promise<AuditLog[]> => {
    return agentAPIClient.listAuditLogs();
  },
}));
