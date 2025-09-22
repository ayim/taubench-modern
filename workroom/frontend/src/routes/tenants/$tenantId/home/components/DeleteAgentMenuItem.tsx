import { FC } from 'react';
import { Menu, useSnackbar } from '@sema4ai/components';
import { useConfirmAction } from '@sema4ai/layouts';
import { IconTrash } from '@sema4ai/icons';
import { components } from '@sema4ai/agent-server-interface';
import { useDeleteAgentMutation } from '@sema4ai/spar-ui/queries';

type DeleteAgentMenuItemProps = {
  agent: components['schemas']['AgentCompat'];
  tenantId: string;
};

export const DeleteAgentMenuItem: FC<DeleteAgentMenuItemProps> = ({ agent }) => {
  const deleteAgentMutation = useDeleteAgentMutation({});
  const { addSnackbar } = useSnackbar();

  const onDeleteConfirm = useConfirmAction(
    {
      title: `Delete Agent`,
      text: `Are you sure you want to delete "${agent.name}"? This action cannot be undone.`,
      confirmActionText: 'Delete',
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
    <Menu.Item
      onClick={(e) => {
        e.stopPropagation();
        handleDelete();
      }}
      icon={IconTrash}
    >
      Delete
    </Menu.Item>
  );
};
