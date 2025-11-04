import { Box, Button, Input, Typography, useDebounce } from '@sema4ai/components';
import { SidebarMenu, useSidebarMenu } from '@sema4ai/layouts';
import { styled } from '@sema4ai/theme';
import { FC, useMemo, useState } from 'react';

import { IconCloseSmall, IconSearch } from '@sema4ai/icons';
import { useParams } from '../../../hooks';
import { useWorkItemsInfiniteQuery } from '../../../queries/workItems';
import { NewWorkItem } from './NewWorkItem';
import { WorkerItem } from './WorkerItem';
import { VirtualList } from '../../../common/VirtualList';

const WorkItemSearchButton = styled(Button)<{ $expanded: boolean }>`
  position: absolute;
  right: ${({ theme, $expanded }) => ($expanded ? theme.space.$48 : theme.space.$12)};
  top: ${({ theme }) => theme.space.$12};
`;

export const WorkerList: FC = () => {
  const { agentId } = useParams('/workItem/$agentId/$workItemId/$threadId');
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
      <Box display="flex" flexDirection="column" height="100%" overflow="hidden">
        <Box>
          <Box display="flex" alignItems="center" justifyContent="space-between" p="$8">
            <Typography variant="body-medium" fontWeight="medium">
              Work Items
            </Typography>
          </Box>
          {!filteringWorkItem ? (
            <WorkItemSearchButton
              $expanded={workItemsListExpanded}
              variant="ghost-subtle"
              icon={IconSearch}
              onClick={startWorkItemFilter}
              aria-label="work-item-search"
            />
          ) : (
            <Box px={1}>
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
        <Box display="flex" flexDirection="column" flex="1" minHeight="0" overflow="hidden">
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
        </Box>
      </Box>
    </SidebarMenu>
  );
};
