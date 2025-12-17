import { FC } from 'react';
import { Box, Grid } from '@sema4ai/components';
import { AgentIcon, AgentCard } from '@sema4ai/layouts';
import { IconMcp } from '@sema4ai/icons/logos';
import { IconActions } from '@sema4ai/icons';
import { components } from '@sema4ai/agent-server-interface';

type Props = {
  agentTemplate: components['schemas']['AgentPackageInspectionResponse'];
};

export const AgentOverviewStep: FC<Props> = ({ agentTemplate }) => {
  const agentMode = (agentTemplate.metadata as { mode?: 'worker' | 'conversational' } | undefined)?.mode;
  const agentType = agentMode === 'worker' ? 'Worker' : 'Conversational';

  return (
    <Box>
      <AgentCard
        illustration={<AgentIcon mode={agentMode} variant="brand" />}
        version={agentTemplate.version}
        title={agentTemplate.name}
        description={agentTemplate.description}
      >
        <AgentCard.Content>
          <AgentCard.ActionPackageList>
            {agentTemplate.action_packages?.map((actionPackage) => (
              <AgentCard.ActionPackageList.Item
                key={`${actionPackage.name}-${actionPackage.version}`}
                illustration={actionPackage.icon ? actionPackage.icon : <IconActions size="m" />}
                name={actionPackage.name}
                description={actionPackage.description}
                version={actionPackage.version}
                actions={actionPackage.actions ?? []}
                queries={[]}
                mcpTools={[]}
              />
            ))}
          </AgentCard.ActionPackageList>

          {/* MCP servers overview (top) */}
          {(agentTemplate.mcp_servers?.length ?? 0) > 0 && (
            <Box mb="$24" display="flex" flexDirection="column" gap="$16">
              {agentTemplate.mcp_servers?.map((srv, idx) => (
                <Box key={`${srv.name}-${idx}`} display="flex" flexDirection="column" gap="$6">
                  <Box display="flex" gap="$8" alignItems="center">
                    <IconMcp />
                    <Box>
                      <Box fontWeight="600">{srv.name}</Box>
                      <Box color="content.subtle" fontSize="$12">
                        Interact with remote MCP Server • Transport: {srv.transport}
                      </Box>
                    </Box>
                  </Box>
                </Box>
              ))}
            </Box>
          )}

          <Grid columns={[1, 2, 3]} gap="$24">
            <AgentCard.Kpi label="Agent Type" value={agentType} />
            <AgentCard.Kpi label="Large Language Model" value={agentTemplate.model.name ?? 'Unknown'} />
          </Grid>
        </AgentCard.Content>
      </AgentCard>
    </Box>
  );
};
