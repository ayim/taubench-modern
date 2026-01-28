import { Box, Button, Menu, Typography, useSnackbar } from '@sema4ai/components';
import { IconDotsHorizontal, IconStatusCompleted, IconStatusError } from '@sema4ai/icons';
import { IconGoogle, IconMicrosoft, IconSalesforce, IconSlack, IconZendesk } from '@sema4ai/icons/logos';
import { OAuthProvider } from '@sema4ai/oauth-client';
import { useParams } from '@tanstack/react-router';
import { snakeCaseToTitleCase } from '~/components/helpers';
import { AgentOAuthProviderState } from '../../../lib/OAuth';
import { useDeleteAgentOAuthMutation } from '~/queries/agents';
import { authorizeOAuthProvider } from '~/utils/oAuth';

const getOAuthProviderIcon = (provider: OAuthProvider): React.ReactNode | null => {
  switch (provider) {
    case OAuthProvider.google:
      return <IconGoogle />;
    case OAuthProvider.microsoft:
      return <IconMicrosoft />;
    case OAuthProvider.slack:
      return <IconSlack />;
    case OAuthProvider.zendesk:
      return <IconZendesk />;
    case OAuthProvider.salesforce:
      return <IconSalesforce />;
    default:
      return null;
  }
};

export const OAuthProviderSection = ({ agentOAuthState }: { agentOAuthState: AgentOAuthProviderState[] }) => {
  const { agentId } = useParams({ strict: false });
  const { addSnackbar } = useSnackbar();

  const { mutate: deleteAgentOAuth } = useDeleteAgentOAuthMutation({ agentId });

  const onConnect = (uri: string) => {
    authorizeOAuthProvider(uri);
  };

  const onDelete = (connectionId: string) => {
    deleteAgentOAuth(
      { connectionId },
      {
        onSuccess: () => {
          addSnackbar({
            message: 'OAuth connection deleted successfully',
            variant: 'success',
          });
        },
        onError: () => {
          addSnackbar({
            message: 'Failed to delete OAuth connection',
            variant: 'danger',
          });
        },
      },
    );
  };

  return (
    <Box display="flex" flexDirection="column" gap="$10">
      <Typography variant="body-medium" fontWeight="bold">
        Permissions
      </Typography>
      {agentOAuthState.length > 0 ? (
        <Box display="flex" flexDirection="column" gap="$10">
          {agentOAuthState.map((provider) => (
            <Box display="flex" justifyContent="space-between" alignItems="center">
              <Box display="flex" gap="$8">
                {getOAuthProviderIcon(provider.providerType)}
                <Typography variant="body-medium">{snakeCaseToTitleCase(provider.providerType)}</Typography>
              </Box>
              <Box display="flex" alignItems="center" gap="$4">
                {provider.isAuthorized ? (
                  <IconStatusCompleted color="content.success" />
                ) : (
                  <IconStatusError color="content.error" />
                )}

                <Menu
                  trigger={
                    <Button icon={IconDotsHorizontal} variant="outline" size="small" round aria-label="Actions" />
                  }
                >
                  {!provider.isAuthorized ? (
                    <Menu.Item onClick={() => onConnect(provider.uri)}>Connect</Menu.Item>
                  ) : (
                    <Menu.Item onClick={() => onDelete(provider.id)}>Delete</Menu.Item>
                  )}
                </Menu>
              </Box>
            </Box>
          ))}
        </Box>
      ) : (
        <Typography variant="body-medium">No permissions required.</Typography>
      )}
    </Box>
  );
};
