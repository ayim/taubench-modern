import { createFileRoute } from '@tanstack/react-router';
// import { DocumentIntelligence } from '@sema4ai/agent-components'

export const Route = createFileRoute('/$tenantId/docIntel/')({
  component: DocIntelPage,
});

function DocIntelPage() {
  return <div>DocIntelPage</div>;
  //   return <DocumentIntelligence />;
}
