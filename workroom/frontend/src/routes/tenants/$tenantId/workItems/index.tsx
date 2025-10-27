import { createFileRoute, useNavigate, useParams, useSearch } from '@tanstack/react-router';
import { WorkItemsTable, WorkItemsOverview } from '@sema4ai/spar-ui';
import { Tabs } from '@sema4ai/components';

import { Page } from '~/components/layout/Page';
import { downloadJSON } from '~/lib/utils';

type WorkItemsSearch = {
  tab: 'all' | 'overview';
  agent?: string;
  status?: string | string[];
  search?: string;
  page?: number;
};

export const Route = createFileRoute('/tenants/$tenantId/workItems/')({
  component: WorkItems,
  validateSearch: (search: Record<string, unknown>): WorkItemsSearch => {
    return {
      tab: (search.tab as 'all' | 'overview') || 'all',
      agent: search.agent as string | undefined,
      status: search.status as string | string[] | undefined,
      search: search.search as string | undefined,
      page: search.page ? Number(search.page) : undefined,
    };
  },
});

function WorkItems() {
  const navigate = useNavigate();
  const { tenantId } = useParams({ from: '/tenants/$tenantId/workItems/' });
  const search = useSearch({ from: '/tenants/$tenantId/workItems/' });

  const activeTab = search.tab === 'overview' ? 1 : 0;

  const handleTabChange = (index: number) => {
    const newTab = index === 0 ? 'all' : 'overview';
    navigate({
      to: '/tenants/$tenantId/workItems',
      params: { tenantId },
      search: { tab: newTab },
    });
  };

  return (
    <Page title="Work Items">
      <Tabs activeTab={activeTab} setActiveTab={handleTabChange}>
        <Tabs.Tab>All Work Items</Tabs.Tab>
        <Tabs.Tab>Overview</Tabs.Tab>
        <Tabs.Panel>
          <WorkItemsTable onDownloadJSON={downloadJSON} />
        </Tabs.Panel>
        <Tabs.Panel>
          <WorkItemsOverview />
        </Tabs.Panel>
      </Tabs>
    </Page>
  );
}
