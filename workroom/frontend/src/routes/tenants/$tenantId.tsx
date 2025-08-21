import { useMemo, useState } from 'react';
import { Outlet, createFileRoute, redirect } from '@tanstack/react-router';
import { Box, Button, EmptyState } from '@sema4ai/components';
import { DocumentAPIProvider, MarkdownRes, DocTypeContextProvider } from '@sema4ai/agent-components';
import { getDocumentAPIClient } from '~/lib/DocumentAPIClient';
import { getListAgentsQueryOptions } from '~/queries/agents';
import { TenantContext } from '~/lib/tenantContext';
import errorIllustration from '~/assets/error.svg';
import { Content } from '../components/Content';
import { Header } from '../components/Header';
import { Main } from '../components/Main';
import { Sidebar } from '../components/Sidebar';
import { getTenantWorkoomRedirect } from '~/lib/utils';
import { getMeta } from '~/lib/meta';

export const Route = createFileRoute('/tenants/$tenantId')({
  loader: async ({ context: { queryClient, agentAPIClient }, params: { tenantId } }) => {
    const agents = await queryClient.ensureQueryData(
      getListAgentsQueryOptions({
        agentAPIClient,
        tenantId,
      }),
    );

    const tenantMeta = await agentAPIClient.getTenantMeta(tenantId);
    const applicationMeta = await getMeta();

    const tenant = await agentAPIClient.getTenant(tenantId);

    const workroomRedirect = tenant ? getTenantWorkoomRedirect({ tenant, location }) : null;

    if (workroomRedirect) {
      throw redirect({
        href: workroomRedirect.href,
      });
    }

    return {
      agents,
      tenantMeta: tenantMeta
        ? {
            ...tenantMeta,
            branding: applicationMeta.branding,
          }
        : undefined,
    };
  },
  component: View,
});

function View() {
  const [apiResponse, setApiResponse] = useState<MarkdownRes>({} as MarkdownRes);
  const [isNewDocumentType, setIsNewDocumentType] = useState<boolean>(false);
  const [pdfFile, setPdfFile] = useState<File | undefined>(undefined);
  const { agents, tenantMeta } = Route.useLoaderData();

  const { tenantId } = Route.useParams();
  const { agentAPIClient } = Route.useRouteContext();
  const documentClient = useMemo(() => getDocumentAPIClient(tenantId, agentAPIClient), [tenantId, agentAPIClient]);

  const docTypeContextValue = useMemo(
    () => ({
      apiResponse,
      setApiResponse,
      isNewDocumentType,
      setIsNewDocumentType,
      pdfFile,
      setPdfFile,
    }),
    [apiResponse, setApiResponse, isNewDocumentType, setIsNewDocumentType, pdfFile, setPdfFile],
  );

  if (!tenantMeta) {
    return (
      <Box display="flex" justifyContent="center" flexDirection="column" maxHeight={960} height="calc(100% - 72px)">
        <EmptyState
          illustration={<img src={errorIllustration} loading="lazy" alt="" />}
          title="Internal error"
          description="Workspace data could not be loaded."
          action={
            <Button onClick={() => window.location.reload()} round>
              Reload page
            </Button>
          }
        />
      </Box>
    );
  }

  return (
    <TenantContext.Provider value={tenantMeta}>
      <Main>
        <Header />
        <Sidebar agents={agents} />
        <section className="bg-[url('/img/background.png')] bg-cover">
          <Content>
            <DocTypeContextProvider value={docTypeContextValue}>
              <DocumentAPIProvider value={documentClient}>
                <Outlet />
              </DocumentAPIProvider>
            </DocTypeContextProvider>
          </Content>
        </section>
      </Main>
    </TenantContext.Provider>
  );
}
