import { FC, useMemo } from 'react';
import { Box, Progress, useSnackbar } from '@sema4ai/components';
import { components } from '@sema4ai/agent-server-interface';

import { Accordion } from '~/components/Accordion';
import { useAgentQuery, useUpdateAgentMutation } from '~/queries/agents';
import { UserRole, useUserRole } from '~/hooks/useUserRole';

import { AgentName } from './components/AgentName';
import { ConversationStarter } from './components/ConversationStarter';
import { LLM } from './components/LLM';
import { MCPServers } from './components/MCPServers';
import { Runbook } from './components/Runbook';
import { SemanticData } from './components/SemanticData';
import { AgentDetailsContext } from './components/context';
import { Endpoints } from './components/Endpoints';
import { DocumentIntelligence } from './components/DocumentIntelligence';
import { DataFrames } from './components/DataFrames';

export const ChatDetails: FC<{ agentId: string }> = ({ agentId }) => {
  const { addSnackbar } = useSnackbar();
  const hasAdminRole = useUserRole(UserRole.Admin);
  const { data: agent, isLoading: isAgentLoading } = useAgentQuery({ agentId });
  const { mutateAsync: updateAgent, isPending: isUpdatingAgent } = useUpdateAgentMutation({ agentId });

  const agentDetailsContextValue = useMemo(
    () =>
      agent
        ? {
            agent,
            updateAgent: async (payload: Partial<components['schemas']['UpsertAgentPayload']>) => {
              await updateAgent(
                { payload },
                {
                  onSuccess: () => {
                    addSnackbar({ message: 'Agent updated successfully', variant: 'success' });
                  },
                  onError: (error) => {
                    addSnackbar({ message: error.message, variant: 'danger' });
                  },
                },
              );
            },
          }
        : null,
    [agent],
  );

  if (isAgentLoading || !agent || !agentDetailsContextValue) {
    return (
      <Box display="flex" height="100%" justifyContent="center" alignItems="center">
        <Progress />
      </Box>
    );
  }

  return (
    <Box height="100%" overflow="auto">
      {isUpdatingAgent && <Progress variant="page" />}
      <AgentDetailsContext.Provider value={agentDetailsContextValue}>
        <Box display="flex" flexDirection="column" gap="$24" p="$8" flex="1">
          <AgentName />
          <Runbook />
          <SemanticData />
          <LLM />
          <MCPServers />
          {hasAdminRole && (
            <Box>
              <Accordion title="Advanced Options" size="small">
                <Box display="flex" flexDirection="column" gap="$24">
                  <DocumentIntelligence />
                  <DataFrames />
                  <Endpoints />
                  <ConversationStarter />
                </Box>
              </Accordion>
            </Box>
          )}
        </Box>
      </AgentDetailsContext.Provider>
    </Box>
  );
};
