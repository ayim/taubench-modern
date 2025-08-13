import { FC } from 'react';
import { Box, Header, Grid } from '@sema4ai/components';
import { AgentIcon, AgentCard } from '@sema4ai/layouts';
import { IconMcp } from '@sema4ai/icons/logos';
import { IconLightning } from '@sema4ai/icons';
import { useFormContext } from 'react-hook-form';
import { AgentDeploymentFormSchema } from './context';
import { mockLLMProviders } from './agent-deployment';

// Mock agent template type
type MockAgentTemplate = {
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
  agentTemplate: MockAgentTemplate;
};

export const WizardStep1: FC<Props> = ({ agentTemplate }) => {
  const { watch } = useFormContext<AgentDeploymentFormSchema>();
  const formData = watch();

  const selectedLLM = mockLLMProviders.find((llm) => llm.value === formData.llmId);
  const llmLabel = selectedLLM ? selectedLLM.label : 'Not selected';
  const agentType = agentTemplate.metadata.mode === 'worker' ? 'Worker' : 'Conversational';
  // counts omitted in this design
  // No API key display in the review screen per spec

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
