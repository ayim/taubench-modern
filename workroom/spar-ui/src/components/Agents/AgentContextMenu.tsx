import { components } from '@sema4ai/agent-server-interface';
import { Button, Menu, useSnackbar } from '@sema4ai/components';
import { useDeleteConfirm } from '@sema4ai/layouts';
import { IconDotsHorizontal } from '@sema4ai/icons';

import { useDeleteAgentMutation } from '../../queries';

type Props = {
  agent: components['schemas']['AgentCompat'];
  onAgentDelete?: () => void;
};

/**
 * Displays single Agent related actions context menu
 */
export const AgentContextMenu = ({ agent, onAgentDelete }: Props) => {
  const deleteAgentMutation = useDeleteAgentMutation({});
  const { addSnackbar } = useSnackbar();

  const onDeleteConfirm = useDeleteConfirm(
    {
      entityName: agent.name,
      entityType: 'agent',
    },
    [],
  );

  const handleDelete = onDeleteConfirm(() => {
    if (!agent.id) {
      return;
    }

    deleteAgentMutation.mutate(
      { agentId: agent.id },
      {
        onSuccess: () => {
          addSnackbar({
            message: 'Agent deleted successfully',
            variant: 'success',
          });
          onAgentDelete?.();
        },
        onError: () => {
          addSnackbar({
            message: 'Failed to delete agent',
            variant: 'danger',
          });
        },
      },
    );
  });

  return (
    <Menu trigger={<Button size="small" icon={IconDotsHorizontal} aria-label="More" round variant="ghost" />}>
      <Menu.Item
        onClick={(e) => {
          e.stopPropagation();
          handleDelete();
        }}
      >
        Delete
      </Menu.Item>
    </Menu>
  );
};
