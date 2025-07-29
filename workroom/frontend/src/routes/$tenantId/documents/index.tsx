import { DocumentTypes } from '@sema4ai/agent-components';
import { Box, Button, EmptyState } from '@sema4ai/components';
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router';

import errorIllustration from '~/assets/error.svg';
import { TransitionLoader } from '~/components/Loaders';
import { useTenantContext } from '~/lib/tenantContext';

export const Route = createFileRoute('/$tenantId/documents/')<{ type?: string }>({
  component: View,
});

function View() {
  const { tenantId } = Route.useParams();
  const navigate = useNavigate();
  const { features } = useTenantContext();

  const handleClick = (type: string, tabName: string, markdownResponse?: string) => {
    navigate({
      to: '/$tenantId/documents/documentType',
      params: { tenantId },
      search: { tabName, type },
      state: { __tempKey: markdownResponse },
    });
  };

  if (!features.documentIntelligence.enabled) {
    return (
      <Box display="flex" justifyContent="center" flexDirection="column" maxHeight={960} height="calc(100% - 72px)">
        <EmptyState
          illustration={<img src={errorIllustration} loading="lazy" alt="" />}
          title="Page not available"
          description="Document Intelligence is not enabled for your Workspace"
          action={
            <Link to="/">
              <Button forwardedAs="span" round>
                Return to Home
              </Button>
            </Link>
          }
        />
      </Box>
    );
  }

  return (
    <div className="overflow-auto">
      <DocumentTypes handleClick={handleClick} LoaderComponent={TransitionLoader} />
    </div>
  );
}
