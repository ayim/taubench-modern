import { FC, useMemo } from 'react';
import { Box, Header, Grid } from '@sema4ai/components';
import { AgentIcon, AgentCard } from '@sema4ai/layouts';
import { IconMcp } from '@sema4ai/icons/logos';
import { IconLightning } from '@sema4ai/icons';
import { useFormContext } from 'react-hook-form';
import { useParams, useRouteContext } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import type { paths } from '@sema4ai/agent-server-interface';
import { AgentDeploymentFormSchema } from './context';

// Mock agent template type
type AgentTemplate = {
  id: string;
  name: string;
  description: string;
  metadata: { mode: 'worker' | 'conversational' };
  actions: Array<{ id: string; name: string }>;
  mcpServers: Array<{
    config: {
      name: string;
      url: string;
      transport: 'sse' | 'streamable-http';
      headers: unknown;
    };
  }>;
  dataSources: Array<{
    id: string;
    engine: string;
    name: string;
  }>;
};

type Props = {
  agentTemplate: AgentTemplate;
};

export const WizardStep1: FC<Props> = ({ agentTemplate }) => {
  const { watch } = useFormContext<AgentDeploymentFormSchema>();
  const formData = watch();
  const { tenantId } = useParams({ from: '/tenants/$tenantId/agents/create' });
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  type GetPlatformResponse =
    paths['/api/v2/platforms/{platform_id}']['get']['responses']['200']['content']['application/json'];

  const llmId = formData.llmId;
  const isPackageRef = typeof llmId === 'string' && llmId.startsWith('package:');

  const platformQuery = useQuery({
    queryKey: ['platform', tenantId, llmId],
    queryFn: async (): Promise<GetPlatformResponse> => {
      return (await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/platforms/{platform_id}', {
        params: { path: { platform_id: llmId as string } },
        silent: true,
      })) as GetPlatformResponse;
    },
    enabled: Boolean(llmId) && !isPackageRef,
  });

  const llmLabel = useMemo(() => {
    if (!llmId) return 'Not selected';
    if (isPackageRef) {
      const [, provider, model] = String(llmId).split(':');
      return `${provider} (${model})`;
    }
    if (platformQuery.data?.name) {
      const p = platformQuery.data;
      return `${p.name}${p.kind ? ` (${p.kind})` : ''}`;
    }
    if (platformQuery.isPending) return 'Loading...';
    return String(llmId);
  }, [llmId, isPackageRef, platformQuery.data, platformQuery.isPending]);
  const agentType = agentTemplate.metadata.mode === 'worker' ? 'Worker' : 'Conversational';

  return (
    <Box>
      <AgentCard
        illustration={<AgentIcon mode={agentTemplate.metadata.mode} />}
        version="1.4.2"
        title={formData.name || agentTemplate.name}
        description={formData.description || agentTemplate.description}
      >
        <AgentCard.Content>
          {/* MCP servers overview (top) */}
          {agentTemplate.mcpServers.length > 0 && (
            <Box mb="$24" display="flex" flexDirection="column" gap="$16">
              {agentTemplate.mcpServers.map((srv, idx) => (
                <Box key={`${srv.config.name}-${idx}`} display="flex" flexDirection="column" gap="$6">
                  <Box display="flex" gap="$8" alignItems="center">
                    <IconMcp />
                    <Box>
                      <Box fontWeight="600">{srv.config.name}</Box>
                      <Box color="content.subtle" fontSize="$12">
                        Interact with remote MCP Server • Transport: {srv.config.transport}
                      </Box>
                    </Box>
                  </Box>
                  {Array.isArray((srv.config as unknown as { tools?: Array<{ name: string }> }).tools) && (
                    <Box display="flex" gap="$8" flexWrap="wrap">
                      {((srv.config as unknown as { tools: Array<{ name: string }> }).tools || []).map(
                        (tool: { name: string }) => (
                          <Box
                            key={tool.name}
                            display="flex"
                            alignItems="center"
                            gap="$4"
                            borderColor="border.subtle"
                            borderRadius="$8"
                            p="$4"
                          >
                            <IconLightning />
                            {tool.name}
                          </Box>
                        ),
                      )}
                    </Box>
                  )}
                </Box>
              ))}
            </Box>
          )}
          <Header>
            <Header.Title title="Agent configuration" />
          </Header>

          <Grid columns={[1, 2, 3]} gap="$24">
            <AgentCard.Kpi label="Agent Type" value={agentType} />
            <AgentCard.Kpi label="Large Language Model" value={llmLabel} />
          </Grid>
        </AgentCard.Content>
      </AgentCard>
    </Box>
  );
};
