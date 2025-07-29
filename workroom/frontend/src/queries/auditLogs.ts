import { queryOptions } from '@tanstack/react-query';
import { components as workroomComponents } from '@sema4ai/workroom-interface';

import { QueryProps } from './shared';

type AuditLog = workroomComponents['schemas']['AuditLog'];

export const getListAuditLogsQueryKey = (tenantId: string) => [tenantId, 'auditLogs'];

export const getListAuditLogsQueryOptions = ({ tenantId, agentAPIClient }: QueryProps<{ tenantId: string }>) =>
  queryOptions({
    queryKey: getListAuditLogsQueryKey(tenantId),
    queryFn: async (): Promise<AuditLog[]> => {
      return agentAPIClient.listAuditLogs(tenantId);
    },
  });
