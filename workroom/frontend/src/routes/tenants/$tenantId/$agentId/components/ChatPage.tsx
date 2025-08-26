import { AgentOAuthPermission, operations } from '@sema4ai/workroom-interface';
import {
  ApiClientProvider,
  DocumentAPIProvider,
  ChatPage as ChatPageComponent,
  OAuthOptions,
} from '@sema4ai/agent-components';
import '@sema4ai/agent-components/index.css';
import { OAuthProvider, OAuthProviderSettings } from '@sema4ai/oauth-client';

import { useNavigate } from '@tanstack/react-router';
import { FC, useCallback, useMemo } from 'react';
import { queryClient } from '~/components/providers/QueryClient';
import { AgentAPIClient } from '~/lib/AgentAPIClient';
import { getChatAPIClient } from '~/lib/chatAPIclient';
import { useTenantContext } from '~/lib/tenantContext';
import { getDocumentAPIClient } from '~/lib/DocumentAPIClient';
import { useDeleteOAuthConnection } from '~/queries/oauth';
import { getListAgentPermissionsQueryKey } from '~/queries/permissions';
import { isProviderConfigured } from '~/utils';

const getCurrentQueryParams = () => {
  const searchParams = new URLSearchParams(window.location.search);
  const params: { [key: string]: string } = {};
  // Iterate over each parameter and store in object
  searchParams.forEach((value, key) => {
    if (value) params[key] = value;
  });

  return params;
};
// mocked out. we need to fetch this from the backend
const defaultProviderSettings: Record<OAuthProvider, Partial<OAuthProviderSettings>> = Object.fromEntries(
  Object.keys(OAuthProvider).map((provider) => [
    provider,
    {
      clientId: '-',
      clientSecret: '',
      redirectUri: 'http://localhost:4567',
    },
  ]),
) as Record<OAuthProvider, Partial<OAuthProviderSettings>>;

type Props = {
  tenantId: string;
  threadId?: string;
  workItemId?: string;
  agentId: string;
  agentMeta?: operations['getAgentMeta']['responses'][200]['content']['application/json'];
  agentAPIClient: AgentAPIClient;
  permissions: AgentOAuthPermission[];
  initialThreadMessage?: string;
  readOnlyMode?: {
    enabled: boolean;
    reason: string;
  };
};

export const ChatPage: FC<Props> = ({
  tenantId,
  threadId,
  workItemId,
  agentId,
  agentMeta,
  agentAPIClient,
  permissions,
  initialThreadMessage,
  readOnlyMode: initialReadOnlyMode,
}) => {
  const navigate = useNavigate();
  const { branding, features } = useTenantContext();
  const deleteOAuthConnection = useDeleteOAuthConnection();

  const oAuthOptions: OAuthOptions = useMemo(() => {
    const agentOAuthState = permissions.map((permission) => ({
      provider: permission.providerType as OAuthProvider,
      scopes: permission.scopes,
      authorized: permission.isAuthorized,
    }));

    const pendingOAuthConfig =
      agentOAuthState.findIndex(
        (curr) => !curr.authorized || !isProviderConfigured(curr.provider, defaultProviderSettings[curr.provider]),
      ) > -1;

    const linkOAuthProvider = (provider: OAuthProvider) => {
      const oAuthState = permissions.find((curr) => curr.providerType === provider);

      if (!oAuthState) {
        return true;
      }

      if (!oAuthState.isAuthorized) {
        window.location.href = oAuthState.uri;
        return true;
      }

      deleteOAuthConnection.mutateAsync(
        {
          tenantId,
          agentId,
          connectionId: oAuthState.id,
        },
        {
          onSuccess: () => {
            console.log('Invalidating oauth permissions');

            queryClient.invalidateQueries({
              queryKey: getListAgentPermissionsQueryKey(agentId),
            });
          },
        },
      );
      return false;
    };

    return {
      linkOAuthProvider,
      agentOAuthState,
      // Rest of properties are mocked as all OAuth providers should be pre-configued at all times
      providerSettings: defaultProviderSettings,
      pendingOAuthConfig,
      handleConfigure: () => null,
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [permissions]);

  // we need to keep agent.canSendFeedback for back compatibility with old aces
  const isFeedbackEnabled = agentMeta?.workroomUi?.feedback.enabled || agentMeta?.canSendFeedback;
  const apiClient = useMemo(() => {
    return getChatAPIClient(tenantId || '', agentAPIClient, {
      isDeveloperModeEnabled: features.developerMode.enabled,
      isFeedbackEnabled,
      isAgentDetailsEnabled: features.agentDetails.enabled,
    });
  }, [agentAPIClient, tenantId, features.developerMode.enabled, isFeedbackEnabled, features.agentDetails.enabled]);

  const navigateToThread = useCallback(
    (threadId: string) => {
      const currentQueryParams = getCurrentQueryParams();

      navigate({
        from: '/tenants/$tenantId/$agentId/',
        to: '/tenants/$tenantId/$agentId/$threadId',
        params: { threadId },
        search: currentQueryParams,
      });
    },
    [navigate],
  );

  const navigateToDocumentDashboard = useCallback(() => {
    alert('Unsupported');
  }, []);

  const readOnlyMode = useMemo(() => {
    if (!agentMeta?.workroomUi) {
      return initialReadOnlyMode;
    }
    return agentMeta?.workroomUi.chatInput.enabled === false
      ? {
          enabled: true,
          reason: agentMeta.workroomUi.chatInput.message,
        }
      : initialReadOnlyMode;
  }, [agentMeta?.workroomUi, initialReadOnlyMode]);

  const documentClient = useMemo(() => getDocumentAPIClient(tenantId, agentAPIClient), [tenantId, agentAPIClient]);

  return (
    <DocumentAPIProvider value={documentClient}>
      <ApiClientProvider value={apiClient}>
        <ChatPageComponent
          tenantId={tenantId}
          agentId={agentId}
          threadId={threadId}
          workitemId={workItemId}
          oAuthOptions={oAuthOptions}
          navigateToThread={navigateToThread}
          readOnlyMode={readOnlyMode}
          agentAvatarUrl={branding?.agentAvatarUrl}
          navigateToDocumentDashboard={navigateToDocumentDashboard}
          initialThreadMessage={initialThreadMessage}
        />
      </ApiClientProvider>
    </DocumentAPIProvider>
  );
};
