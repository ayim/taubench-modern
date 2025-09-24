import { Box, Typography } from '@sema4ai/components';
import { IconStatusCompleted, IconStatusError } from '@sema4ai/icons';
import { IconGoogle, IconMicrosoft, IconSalesforce, IconSlack, IconZendesk } from '@sema4ai/icons/logos';
import { OAuthProvider } from '@sema4ai/oauth-client';
import { snakeCaseToTitleCase } from '../../../common/helpers';
import { AgentOAuthProviderState } from '../../../lib/OAuth';

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
              {provider.isAuthorized ? (
                <IconStatusCompleted color="content.success" />
              ) : (
                <IconStatusError color="content.error" />
              )}
            </Box>
          ))}
        </Box>
      ) : (
        <Typography variant="body-medium">No permissions required.</Typography>
      )}
    </Box>
  );
};
