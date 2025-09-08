import { useEffect } from 'react';
import { useSnackbar } from '@sema4ai/components';
import { createFileRoute, useNavigate } from '@tanstack/react-router';

import { InlineLoader } from '~/components/Loaders';

export const Route = createFileRoute('/tenants/$tenantId/oauth')({
  component: View,
});

function View() {
  const { agentAPIClient } = Route.useRouteContext();
  const navigate = useNavigate();
  const { addSnackbar } = useSnackbar();

  useEffect(() => {
    const initAuth = async () => {
      const urlParams = new URLSearchParams(window.location.search);
      const state = urlParams.get('state');

      if (!state) {
        throw new Error('Unexpected: missing state from url');
      }

      const decodedState = atob(state);

      const { agentId, tenantId } = JSON.parse(decodedState) as {
        tenantId: string;
        agentId: string;
      };

      const result = await agentAPIClient.authorizeOAuth({
        tenantId,
      });

      if (!result.success) {
        if (result.error.code === 'failed_to_get_access_token_spcs') {
          addSnackbar({
            message:
              'Failed to authorize OAuth. Please make sure you have whitelisted the OAuth network rules in your OAuth configuration settings (OAuth -> Configure)',
            variant: 'danger',
          });
        } else {
          addSnackbar({
            message: 'Failed to authorize OAuth. Please try again.',
            variant: 'danger',
          });
        }
      }

      navigate({ to: '/tenants/$tenantId/conversational/$agentId', params: { tenantId, agentId } });
    };
    initAuth();
  }, [agentAPIClient, navigate, addSnackbar]);

  return <InlineLoader />;
}
