import { Box, Button, Input, Typography } from '@sema4ai/components';
import { SidebarMenu, useSidebarMenu } from '@sema4ai/layouts';
import { styled } from '@sema4ai/theme';
import { FC, useMemo, useState } from 'react';

import { IconCloseSmall, IconSearch } from '@sema4ai/icons';
import { useParams } from '../../../hooks';
import { useWorkItemsQuery } from '../../../queries/workItems';
import { NewWorkItem } from './NewWorkItem';
import { WorkerItem } from './WorkerItem';
import { ScrollableContainer } from '../../Thread/components/ThreadsList/styles';

const WorkItemSearchButton = styled(Button)<{ $expanded: boolean }>`
  position: absolute;
  right: ${({ theme, $expanded }) => ($expanded ? theme.space.$48 : theme.space.$12)};
  top: ${({ theme }) => theme.space.$12};
`;

export const WorkerList: FC = () => {
  const { agentId } = useParams('/workItem/$agentId/$workItemId/$threadId');
  const { data: workItems, isLoading } = useWorkItemsQuery({ agentId });

  const { expanded: workItemsListExpanded } = useSidebarMenu('work-items-list');
  const [filteringWorkItem, setFilteringWorkItem] = useState(false);
  const [workItemFilterText, setWorkItemFilterText] = useState('');

  const startWorkItemFilter = () => {
    setWorkItemFilterText('');
    setFilteringWorkItem(true);
  };

  const stopWorkItemFilter = () => {
    setWorkItemFilterText('');
    setFilteringWorkItem(false);
  };

  const filteredWorkItems = useMemo(() => {
    const textToSearch = workItemFilterText.toLowerCase().trim();

    return workItems?.filter((workItem) => {
      const { work_item_name: workItemName, work_item_id: workItemId } = workItem;
      const textToSearchInto = (workItemName ?? workItemId).toLowerCase();
      return textToSearchInto.includes(textToSearch);
    });
  }, [workItems, workItemFilterText]);

  // TODO-V2: Loading state for panels?
  if (isLoading) {
    return null;
  }

  return (
    <SidebarMenu name="work-items-list" title="Work Items">
      <Box display="flex" flexDirection="column" height="100%" overflow="hidden">
        <Box>
          <Box display="flex" alignItems="center" justifyContent="space-between" p="$8">
            <Typography variant="body-medium" fontWeight="medium">
              Work Items
            </Typography>
          </Box>
          {!filteringWorkItem && (
            <WorkItemSearchButton
              $expanded={workItemsListExpanded}
              variant="ghost-subtle"
              icon={IconSearch}
              onClick={startWorkItemFilter}
              aria-label="work-item-search"
            />
          )}
          {filteringWorkItem && (
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
          <ScrollableContainer flex="1" minHeight="0">
            {filteredWorkItems?.map((workItem) => (
              <WorkerItem
                key={workItem.work_item_id}
                name={workItem.work_item_name || workItem.work_item_id}
                workItemId={workItem.work_item_id}
              />
            ))}
            {filteredWorkItems?.length === 0 && (
              <Box p="$12">
                <Typography variant="body-small">
                  {filteringWorkItem ? 'No work items found' : 'No work items yet'}
                </Typography>
              </Box>
            )}
          </ScrollableContainer>
        </Box>
      </Box>
    </SidebarMenu>
  );
};
