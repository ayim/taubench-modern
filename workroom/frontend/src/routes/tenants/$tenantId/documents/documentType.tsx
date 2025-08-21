import { createFileRoute, useLocation, useNavigate, useSearch } from '@tanstack/react-router';
import { DocumentTypeDetails } from '@sema4ai/agent-components';
import '@sema4ai/agent-components/index.css';

export const Route = createFileRoute('/tenants/$tenantId/documents/documentType')({
  component: View,
});

function View() {
  const { tenantId } = Route.useParams();
  const name = useSearch({
    from: '/tenants/$tenantId/documents/documentType',
  }) as { type: string };

  const handleClick = (type: string, tabName: string, markdownResponse?: string) => {
    navigate({
      to: '/tenants/$tenantId/documents/documentType',
      params: { tenantId },
      search: { tabName, type },
      state: { __tempKey: markdownResponse },
    });
  };

  const search = useLocation();
  const markdownResponse = search?.state?.__tempKey;

  const navigate = useNavigate();

  // Document ID in UUID format is passed in threadId
  const handleNavigate = (agentId: string, threadId: string) => {
    navigate({ to: '/tenants/$tenantId/$agentId/$threadId', params: { tenantId, agentId, threadId } });
  };

  return (
    <DocumentTypeDetails
      name={name.type}
      handleBack={() => {
        navigate({ to: '/tenants/$tenantId/documents', params: { tenantId } });
      }}
      handleNavigateAgent={handleNavigate}
      markdownRes={markdownResponse}
      handleClick={handleClick}
    />
  );
}
