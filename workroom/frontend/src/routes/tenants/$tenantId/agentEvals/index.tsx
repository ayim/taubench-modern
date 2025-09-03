import { createFileRoute } from '@tanstack/react-router';
import { Box, Header, Scroll } from '@sema4ai/components';

export const Route = createFileRoute('/tenants/$tenantId/agentEvals/')({
  component: AgentEvals,
});

function AgentEvals() {
  return (
    <Scroll>
      <Box p="$24" pb="$48">
        <Header size="x-large">
          <Header.Title title="Agent Evals" />
        </Header>
        Work your magic, Marco!
      </Box>
    </Scroll>
  );
}

export default AgentEvals;
