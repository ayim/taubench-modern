import { FC } from 'react';
import { Box, Grid } from '@sema4ai/components';
import { AgentIcon, AgentCard } from '@sema4ai/layouts';
import { IconMcp } from '@sema4ai/icons/logos';
import { IconActions, IconLightning } from '@sema4ai/icons';
import { AgentPackageResponse } from '../../../home/components/AgentUploadForm';

type Props = {
  agentTemplate: AgentPackageResponse['agentTemplate'];
};

export const AgentOverviewStep: FC<Props> = ({ agentTemplate }) => {
  const agentType = agentTemplate.metadata.mode === 'worker' ? 'Worker' : 'Conversational';

  return (
    <Box>
      <AgentCard
        illustration={<AgentIcon mode={agentTemplate.metadata.mode} />}
        version={agentTemplate.version}
        title={agentTemplate.name}
        description={agentTemplate.description}
      >
        <AgentCard.Content>
          <AgentCard.ActionPackageList>
            {agentTemplate.action_packages.map((actionPackage) => (
              <AgentCard.ActionPackageList.Item
                key={`${actionPackage.name}-${actionPackage.action_package_version}`}
                illustration={actionPackage.icon ? actionPackage.icon : <IconActions size="m" />}
                name={actionPackage.name}
                description={actionPackage.description}
                version={actionPackage.action_package_version}
                actions={actionPackage.actions || []}
                queries={actionPackage.queries || []}
                mcpTools={actionPackage.mcpTools || []}
              />
            ))}
          </AgentCard.ActionPackageList>

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

          <Grid columns={[1, 2, 3]} gap="$24">
            <AgentCard.Kpi label="Agent Type" value={agentType} />
            <AgentCard.Kpi label="Large Language Model" value={agentTemplate.model.name} />
          </Grid>
        </AgentCard.Content>
      </AgentCard>
    </Box>
  );
};
