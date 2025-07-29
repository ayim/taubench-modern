import { createFileRoute } from '@tanstack/react-router';
import { Box, Header, Scroll } from '@sema4ai/components';

import { getListAuditLogsQueryOptions } from '~/queries/auditLogs.ts';
import { AuditLogsTable } from './components/AuditLogsTable';

export const Route = createFileRoute('/$tenantId/auditLogs/')({
  loader: async ({ context: { queryClient, agentAPIClient }, params: { tenantId } }) => {
    const auditLogs = await queryClient.ensureQueryData(
      getListAuditLogsQueryOptions({
        agentAPIClient,
        tenantId,
      }),
    );
    return { auditLogs };
  },
  component: AuditLogs,
});

function AuditLogs() {
  const { auditLogs } = Route.useLoaderData();

  return (
    <Scroll>
      <Box p="$24" pb="$48">
        <Header size="x-large">
          <Header.Title title="Audit Logs" />
        </Header>
        <AuditLogsTable auditLogs={auditLogs} />
      </Box>
    </Scroll>
  );
}

export default AuditLogs;
