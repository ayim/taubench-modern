import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useEffect } from 'react';
import { InlineLoader } from '~/components/Loaders';
import { errorToast } from '~/utils/toasts';

export const Route = createFileRoute('/oauth')({
  component: View,
});

function View() {
  const { agentAPIClient } = Route.useRouteContext();
  const navigate = useNavigate();

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
          errorToast(
            'Failed to authorize OAuth. Please make sure you have whitelisted the OAuth network rules in your OAuth configuration settings (OAuth -> Configure)',
          );
        } else {
          errorToast('Failed to authorize OAuth. Please try again.');
        }
      }

      navigate({ to: '/$tenantId/$agentId', params: { tenantId, agentId } });
    };
    initAuth();
  }, [agentAPIClient, navigate]);

  return <InlineLoader />;
}
