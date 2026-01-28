import { Box, Button, Input, Typography } from '@sema4ai/components';
import { SidebarMenu, useSidebarMenu } from '@sema4ai/layouts';
import { styled } from '@sema4ai/theme';
import { FC, useEffect, useMemo, useState } from 'react';
import { IconCloseSmall, IconSearch } from '@sema4ai/icons';
import { useParams } from '@tanstack/react-router';

import { useThreadsQuery } from '~/queries/threads';
import { NewThreadItem } from '../NewThreadItem';
import { ThreadItem } from '../ThreadItem';
import { Header } from './styles';
import { VirtualList } from '~/components/VirtualList';
import { SIDEBAR_STARTING_WIDTH_PX } from '~/lib/constants';

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

const ThreadSearchButton = styled(Button)<{ $expanded: boolean }>`
  position: absolute;
  right: ${({ theme, $expanded }) => ($expanded ? theme.space.$48 : theme.space.$12)};
  top: ${({ theme }) => theme.space.$12};
`;

export const ThreadsList: FC = () => {
  const { agentId, threadId } = useParams({ strict: false });
  const { data: threads, isLoading, refetch: refetchThreads } = useThreadsQuery({ agentId });

  /**
   * Sometimes it may happen that we are on some valid $threadId,
   * but react-query client does not have it's information in its cache
   * in that case refreshing the threads query so that new list will
   * containe the thread we are on
   */
  useEffect(() => {
    const hasThread = threads?.some((thread) => thread.thread_id === threadId);
    if (!hasThread) {
      refetchThreads();
    }
  }, [threadId]);

  const userInitiatedThreads = threads?.filter((thread) => !thread.metadata?.scenario_id);

  const { expanded: threadsListExpanded } = useSidebarMenu('threads-list');
  const [filteringThread, setFilteringThread] = useState(false);
  const [threadFilterText, setThreadFilterText] = useState('');

  const startThreadFilter = () => {
    setThreadFilterText('');
    setFilteringThread(true);
  };

  const stopThreadFilter = () => {
    setThreadFilterText('');
    setFilteringThread(false);
  };

  const filteredUserInitiatedThreads = useMemo(
    () =>
      userInitiatedThreads?.filter((thread) => {
        return thread.name.toLowerCase().includes(threadFilterText.toLowerCase().trim());
      }),
    [userInitiatedThreads, threadFilterText],
  );

  // TODO-V2: Loading state for panels?
  if (isLoading) {
    return null;
  }

  return (
    <SidebarMenu
      name="threads-list"
      title="Threads list"
      initialWidth={SIDEBAR_STARTING_WIDTH_PX}
      minWidth={SIDEBAR_STARTING_WIDTH_PX}
    >
      <Container>
        <Box display="flex" flexDirection="column" gap="$16">
          <Header>
            <Typography variant="body-large" fontWeight="500">
              History
            </Typography>
          </Header>
          <Box display="flex" flexDirection="column">
            {!filteringThread && (
              <ThreadSearchButton
                $expanded={threadsListExpanded}
                variant="ghost-subtle"
                icon={IconSearch}
                onClick={startThreadFilter}
                aria-label="thread-search"
              />
            )}
            {filteringThread && (
              <Box px={1} pb="$8">
                <Input
                  autoFocus
                  aria-label="thread-search-input"
                  iconLeft={IconSearch}
                  placeholder="Seach Chats"
                  value={threadFilterText}
                  onChange={(e) => setThreadFilterText(e.target.value)}
                  iconRight={IconCloseSmall}
                  onIconRightClick={stopThreadFilter}
                  onKeyDown={(e) => {
                    if (e.key === 'Escape') stopThreadFilter();
                  }}
                  onBlur={() => {
                    if (!threadFilterText.trim()) stopThreadFilter();
                  }}
                  iconRightLabel="close-search"
                  round
                />
              </Box>
            )}
            <NewThreadItem />
          </Box>
        </Box>
        {filteredUserInitiatedThreads && (
          <VirtualListContainer>
            <VirtualList
              items={filteredUserInitiatedThreads}
              renderComponent={ThreadItem}
              itemHeight={36}
              itemKey="thread_id"
            />
          </VirtualListContainer>
        )}
        {filteredUserInitiatedThreads?.length === 0 && (
          <Box p="$12">
            <Typography variant="body-small">{filteringThread ? 'No threads found' : 'No messages yet'}</Typography>
          </Box>
        )}
      </Container>
    </SidebarMenu>
  );
};
