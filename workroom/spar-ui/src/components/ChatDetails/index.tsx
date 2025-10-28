import { components } from '@sema4ai/agent-server-interface';
import { Box, Progress } from '@sema4ai/components';
import { FC } from 'react';
import { useAgentDetailsQuery, useAgentOAuthStateQuery, useAgentQuery } from '../../queries/agents';
import { ActionsSection } from './components/ActionsSection';
import { DescriptionSection } from './components/DescriptionSection';
import { LLMSection } from './components/LLMSection';
import { MCPServerSection } from './components/MCPServerSection';
import { OAuthProviderSection } from './components/OAuthProviderSection';
import RunbookSection from './components/RunbookSection/index';
import { SemanticDataSection } from './components/SemanticDataSection';
import { SparUIFeatureFlag } from '../../api';
import { useFeatureFlag } from '../../hooks';

export type ActionPackage = components['schemas']['ActionPackageDetail'];
export type MCPServer = components['schemas']['MCPServerDetail'];

export const ChatDetails: FC<{ agentId: string }> = ({ agentId }) => {
  const { data: agentDetails, isLoading: isAgentDetailsLoading } = useAgentDetailsQuery({ agentId });
  const { data: agent, isLoading: isAgentLoading } = useAgentQuery({ agentId });
  const { data: agentOAuthState, isLoading: isAgentOAuthStateLoading } = useAgentOAuthStateQuery({ agentId });
  const { enabled: isAgentDetailsEnabled } = useFeatureFlag(SparUIFeatureFlag.agentDetails);

  if (!isAgentDetailsEnabled) return null;

  return (
    <Box height="100%">
      {isAgentDetailsLoading || isAgentLoading || isAgentOAuthStateLoading ? (
        <Box display="flex" justifyContent="center" alignItems="center" height="100%">
          <Progress />
        </Box>
      ) : (
        <Box display="flex" flexDirection="column" gap={20} p={8}>
          {agent?.description && <DescriptionSection description={agent.description} />}
          {agentDetails?.runbook && !!agentDetails.runbook.trim() && (
            <RunbookSection agentName={agent?.name || ''} runbookMarkdown={agentDetails.runbook} />
          )}
          {agentDetails?.action_packages && agentDetails.action_packages.length > 0 && (
            <ActionsSection actionPackages={agentDetails.action_packages} />
          )}
          {agentDetails?.mcp_servers && agentDetails.mcp_servers.length > 0 && (
            <MCPServerSection mcpServers={agentDetails.mcp_servers} />
          )}
          {agentOAuthState && agentOAuthState.length > 0 && <OAuthProviderSection agentOAuthState={agentOAuthState} />}
          {agent?.model && <LLMSection provider={agent.model.provider as string} name={agent.model.name as string} />}

          <SemanticDataSection />
        </Box>
      )}
    </Box>
  );
};
