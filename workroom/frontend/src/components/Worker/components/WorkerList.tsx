import { Box, Button, Input, Typography, useDebounce } from '@sema4ai/components';
import { SidebarMenu, useSidebarMenu } from '@sema4ai/layouts';
import { styled } from '@sema4ai/theme';
import { FC, useMemo, useState } from 'react';
import { useParams } from '@tanstack/react-router';

import { IconCloseSmall, IconSearch } from '@sema4ai/icons';
import { useWorkItemsInfiniteQuery } from '~/queries/workItems';
import { NewWorkItem } from './NewWorkItem';
import { WorkerItem } from './WorkerItem';
import { VirtualList } from '~/components/VirtualList';
import { Header } from '../../Thread/components/ThreadsList/styles';

const Container = styled(Box)`
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  margin: 0 -${({ theme }) => theme.space.$12};
  padding: 0 ${({ theme }) => theme.space.$12};
`;

const VirtualListContainer = styled.div`
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  margin: 0 -${({ theme }) => theme.space.$12};

  > div {
    height: 100%;
    padding: 0 ${({ theme }) => theme.space.$12};
  }
`;

const WorkItemSearchButton = styled(Button)<{ $expanded: boolean }>`
  position: absolute;
  right: ${({ theme, $expanded }) => ($expanded ? theme.space.$48 : theme.space.$12)};
  top: ${({ theme }) => theme.space.$12};
`;

export const WorkerList: FC = () => {
  const { agentId } = useParams({ strict: false });
  const [workItemFilterText, setWorkItemFilterText] = useState('');
  const debouncedFilterText = useDebounce(workItemFilterText, 250);

  const { data, hasNextPage, fetchNextPage, isFetchingNextPage } = useWorkItemsInfiniteQuery({
    agentId,
    nameSearch: debouncedFilterText === '' ? undefined : debouncedFilterText,
    limit: 50,
  });

  const { expanded: workItemsListExpanded } = useSidebarMenu('work-items-list');
  const [filteringWorkItem, setFilteringWorkItem] = useState(false);

  const startWorkItemFilter = () => {
    setWorkItemFilterText('');
    setFilteringWorkItem(true);
  };

  const stopWorkItemFilter = () => {
    setWorkItemFilterText('');
    setFilteringWorkItem(false);
  };

  const allWorkItems = useMemo(() => {
    return data?.pages.flatMap((page) => page.records ?? []) ?? [];
  }, [data]);

  return (
    <SidebarMenu name="work-items-list" title="Work Items">
      <Container>
        <Box display="flex" flexDirection="column" gap="$16">
          <Header>
            <Typography variant="body-large" fontWeight="500">
              Work Items
            </Typography>
          </Header>
          <Box display="flex" flexDirection="column">
            {!filteringWorkItem ? (
              <WorkItemSearchButton
                $expanded={workItemsListExpanded}
                variant="ghost-subtle"
                icon={IconSearch}
                onClick={startWorkItemFilter}
                aria-label="work-item-search"
              />
            ) : (
              <Box px={1} pb="$8">
                <Input
                  autoFocus
                  aria-label="work-item-search-input"
                  iconLeft={IconSearch}
                  placeholder="Seach Chats"
                  value={workItemFilterText}
                  onChange={(e) => setWorkItemFilterText(e.target.value)}
                  iconRight={IconCloseSmall}
                  onIconRightClick={stopWorkItemFilter}
                  onKeyDown={(e) => {
                    if (e.key === 'Escape') stopWorkItemFilter();
                  }}
                  onBlur={() => {
                    if (!workItemFilterText.trim()) stopWorkItemFilter();
                  }}
                  iconRightLabel="close-search"
                  round
                />
              </Box>
            )}
            <NewWorkItem />
          </Box>
        </Box>
        <VirtualListContainer>
          <VirtualList
            items={allWorkItems}
            itemKey="thread_id"
            renderComponent={WorkerItem}
            itemHeight={36}
            pagination={{
              hasMore: hasNextPage,
              isFetchingMore: isFetchingNextPage,
              onLoadMore: () => fetchNextPage(),
            }}
          />
        </VirtualListContainer>
      </Container>
    </SidebarMenu>
  );
};
