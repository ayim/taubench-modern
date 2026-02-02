import { FC, useState } from 'react';
import { Box, Button, Typography } from '@sema4ai/components';
import { oAuthProviderIcons } from '@sema4ai/oauth-client/icons';
import { OAuthProvider } from '@sema4ai/oauth-client';
import { IconInformation } from '@sema4ai/icons';

import { authorizeOAuthProvider } from '~/utils/oAuth';
import { useAgentOAuthStateQuery } from '~/queries/agents';
import { snakeCaseToTitleCase } from '~/components/helpers';
import { DetailsDialog } from './components/DetailsDialog';
import { useVioletChatContext } from '../../../context';

export const OAuth: FC = () => {
  const { agentId } = useVioletChatContext();
  const { data: oAuthState = [] } = useAgentOAuthStateQuery({ agentId });
  const [detailsProvider, setDetailsProvider] = useState<{ provider: OAuthProvider; scopes: string[] } | undefined>(
    undefined,
  );

  const onConnect = (uri: string) => {
    authorizeOAuthProvider(uri);
  };

  const onCloseDetails = () => {
    setDetailsProvider(undefined);
  };

  return (
    <>
      <Box display="flex" flexDirection="column" gap="$16" mb="$16">
        {oAuthState.map(({ providerType, scopes, isAuthorized, uri }) => {
          if (isAuthorized) {
            return null;
          }

          const ProviderIcon = oAuthProviderIcons[providerType];
          const isConfigured = !!uri;

          return (
            <Box
              display="flex"
              flexDirection={['column', 'column', 'row', 'row']}
              gap="$20"
              key={providerType}
              borderRadius="$20"
              p="$20"
              backgroundColor="background.subtle"
              boxShadow="small"
            >
              <Box display="flex" gap="$16">
                <ProviderIcon size={32} />
                <Box>
                  <Typography variant="body-large" mb="$4" fontWeight="medium">
                    {isConfigured ? 'Connect' : 'Configure'} {snakeCaseToTitleCase(providerType)}
                  </Typography>
                  <Typography color="content.subtle">
                    Review the permissions this agent needs and approve access.
                  </Typography>
                </Box>
              </Box>
              <Box ml="auto" alignSelf="center" display="flex" alignItems="center" gap="$8">
                <Button
                  variant="ghost"
                  icon={IconInformation}
                  aria-label="Oauth information"
                  onClick={() => setDetailsProvider({ provider: providerType, scopes })}
                />
                <Button type="button" round onClick={() => onConnect(uri)}>
                  Connect
                </Button>
              </Box>
            </Box>
          );
        })}
      </Box>
      {detailsProvider && (
        <DetailsDialog onClose={onCloseDetails} provider={detailsProvider.provider} scopes={detailsProvider.scopes} />
      )}
    </>
  );
};
