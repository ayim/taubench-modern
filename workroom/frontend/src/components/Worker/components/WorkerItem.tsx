import { components } from '@sema4ai/agent-server-interface';
import { Box, Button, Menu, Tooltip, Typography, useSnackbar } from '@sema4ai/components';
import { IconDotsHorizontal, IconLoading } from '@sema4ai/icons';
import { FC, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from '@tanstack/react-router';

import { RenameDialog } from '~/components/dialogs/RenameDialog';
import { formatDateTime } from '~/components/helpers';
import { ListItemLink } from '~/components/link';
import { useUpdateWorkItemMutation, useWorkItemQuery } from '~/queries/workItems';
import { WORK_ITEM_STATUS_CONFIG } from '../../../constants/workItemStatus';
import { ThreadListLinkContainer } from '../../Thread/components/ThreadsList/styles';

type WorkItem = components['schemas']['WorkItem'];

type WorkItemProps = {
  item: WorkItem;
};

const ToolTipContent: FC<Pick<WorkItem, 'created_at' | 'updated_at' | 'status'> & { name: string }> = ({
  name,
  created_at: createdAt,
  updated_at: updatedAt,
  status,
}) => {
  return (
    <>
      <Typography fontWeight="medium" mb="$4">
        {name}
      </Typography>
      <Box display="flex">
        Status:
        <Typography ml="$8" as="span" fontWeight="medium">
          {status}
        </Typography>
      </Box>
      {createdAt && (
        <Box display="flex">
          Created:
          <Typography ml="$8" as="span" fontWeight="medium">
            {formatDateTime(createdAt)}
          </Typography>
        </Box>
      )}
      {updatedAt && (
        <Box display="flex">
          Last updated:
          <Typography ml="$8" as="span" fontWeight="medium">
            {formatDateTime(updatedAt)}
          </Typography>
        </Box>
      )}
    </>
  );
};

const shouldPollForWorkItemUpdates = (workItem: WorkItem) => {
  if (!workItem.thread_id) {
    return true;
  }

  switch (workItem.status) {
    case 'CANCELLED':
    case 'COMPLETED':
    case 'DRAFT':
    case 'ERROR':
    case 'INDETERMINATE':
    case 'NEEDS_REVIEW':
      return false;
    case 'PENDING':
    case 'EXECUTING':
      return true;
    default:
      workItem.status satisfies never;
      return false;
  }
};

export const WorkerItem: FC<WorkItemProps> = ({ item: workItemFromListing }) => {
  const {
    agentId,
    threadId: threadIdFromParams,
    workItemId: workItemIdFromParams,
    tenantId,
  } = useParams({ strict: false });
  const navigate = useNavigate();

  const { data: workItem } = useWorkItemQuery(
    { workItemId: workItemFromListing.work_item_id },
    {
      initialData: workItemFromListing,
      // Only enable the query when the work item is in a non-final state
      // Otherwise every listing fetch triggers n additional calls
      enabled: shouldPollForWorkItemUpdates(workItemFromListing),
      refetchInterval: ({ state: { data: latestWorkItem } }) => {
        return latestWorkItem && shouldPollForWorkItemUpdates(latestWorkItem) ? 2000 : false;
      },
    },
  );
  const { mutate: updateWorkItem } = useUpdateWorkItemMutation({ agentId });
  const { addSnackbar } = useSnackbar();
  const [isRenaming, setIsRenaming] = useState(false);

  const threadId = workItem?.thread_id;
  const displayName = workItem?.work_item_name || workItem?.work_item_id || '';

  /**
   * When new workitem is created, it doesn't have threadId,
   * after some time threadId is attached to the workitem.
   * When this happens and if we are on that workitem,
   * navigate to the threadId route.
   */
  useEffect(() => {
    if (workItemIdFromParams === workItem?.work_item_id && !threadIdFromParams && threadId) {
      navigate({
        to: '/tenants/$tenantId/worker/$agentId/$workItemId/$threadId',
        params: { agentId, workItemId: workItem.work_item_id, threadId, tenantId },
      });
    }
  }, [threadIdFromParams, workItemIdFromParams, threadId, agentId, workItem?.work_item_id]);

  const onWorkItemRename = (workItemName: string) => {
    updateWorkItem(
      { workItemId: workItem?.work_item_id || '', workItemName },
      {
        onSuccess: () => {
          addSnackbar({
            message: 'Work item renamed successfully',
            variant: 'success',
          });
        },
        onError: () => {
          addSnackbar({
            message: 'Failed to rename work item',
            variant: 'danger',
          });
        },
      },
    );
  };

  const iconForStatus = useMemo(() => {
    if (!workItem) {
      return null;
    }

    const workItemStatusConfig = WORK_ITEM_STATUS_CONFIG[workItem.status];
    const IconComponent = workItemStatusConfig.icon;

    return <IconComponent color={workItemStatusConfig.iconColor} />;
  }, [workItem?.status]);

  if (!threadId) {
    return (
      <ThreadListLinkContainer>
        <ListItemLink
          to="/tenants/$tenantId/worker/$agentId/$workItemId"
          params={{ agentId, workItemId: workItem?.work_item_id }}
          icon={IconLoading}
        >
          {displayName}
        </ListItemLink>
      </ThreadListLinkContainer>
    );
  }

  return (
    <>
      <Tooltip
        text={
          <ToolTipContent
            name={displayName}
            created_at={workItem?.created_at}
            updated_at={workItem?.updated_at}
            status={workItem?.status}
          />
        }
        placement="bottom-end"
        $nowrap
      >
        <ThreadListLinkContainer>
          <ListItemLink
            to="/tenants/$tenantId/worker/$agentId/$workItemId/$threadId"
            params={{ agentId, workItemId: workItem?.work_item_id, threadId }}
            icon={iconForStatus ?? undefined}
            preserveSubroute
            hotkey={
              <Menu
                trigger={
                  <Button variant="ghost" size="small" icon={IconDotsHorizontal} aria-label="Work item actions" />
                }
              >
                <Menu.Item onClick={() => setIsRenaming(true)}>Rename</Menu.Item>
              </Menu>
            }
          >
            {displayName}
          </ListItemLink>
        </ThreadListLinkContainer>
      </Tooltip>
      {isRenaming && (
        <RenameDialog
          onClose={() => setIsRenaming(false)}
          onRename={onWorkItemRename}
          entityName={displayName}
          entityType="Work Item"
        />
      )}
    </>
  );
};
