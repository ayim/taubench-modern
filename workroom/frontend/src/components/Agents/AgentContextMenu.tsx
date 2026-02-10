import { components } from '@sema4ai/agent-server-interface';
import { Button, Menu, useSnackbar } from '@sema4ai/components';
import { useDeleteConfirm } from '@sema4ai/layouts';
import { IconDotsHorizontal } from '@sema4ai/icons';
import { useParams } from '@tanstack/react-router';

import { useDeleteAgentMutation } from '~/queries/agents';
import { useAgentPreferencesStore, selectFavourites } from '~/hooks/useAgentPreferencesStore';
import { useFeatureFlag, FeatureFlag } from '../../hooks';

type Props = {
  agent: components['schemas']['AgentCompat'];
  onAgentDelete?: () => void;
};
/**
 * Displays single Agent related actions context menu
 */
export const AgentContextMenu = ({ agent, onAgentDelete }: Props) => {
  const { tenantId = '' } = useParams({ strict: false });
  const deleteAgentMutation = useDeleteAgentMutation({});
  const { addSnackbar } = useSnackbar();
  const { enabled: isDeploymentWizardEnabled } = useFeatureFlag(FeatureFlag.deploymentWizard);
  const addFavourite = useAgentPreferencesStore((s) => s.addFavourite);
  const removeFavourite = useAgentPreferencesStore((s) => s.removeFavourite);
  const favourites = useAgentPreferencesStore((s) => selectFavourites(s, tenantId));
  const agentIsFavourite = agent.id ? favourites.includes(agent.id) : false;

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
          if (agent.id) {
            if (agentIsFavourite) {
              removeFavourite(tenantId, agent.id);
            } else {
              addFavourite(tenantId, agent.id);
            }
          }
        }}
      >
        {agentIsFavourite ? 'Remove from Favourites' : 'Add to Favourites'}
      </Menu.Item>
      {isDeploymentWizardEnabled && (
        <Menu.Item
          onClick={(e) => {
            e.stopPropagation();
            handleDelete();
          }}
        >
          Delete
        </Menu.Item>
      )}
    </Menu>
  );
};
