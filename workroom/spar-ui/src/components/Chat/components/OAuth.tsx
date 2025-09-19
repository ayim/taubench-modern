import { FC } from 'react';
import { Box, Button, Typography } from '@sema4ai/components';
import { oAuthProviderIcons } from '@sema4ai/oauth-client/icons';

import { useAgentOAuthStateQuery } from '../../../queries/agents';
import { useParams } from '../../../hooks/useParams';
import { useSparUIContext } from '../../../api/context';

export const OAuth: FC = () => {
  const { agentId } = useParams('/thread/$agentId/$threadId');
  const { data: oAuthState = [] } = useAgentOAuthStateQuery({ agentId });
  const { sparAPIClient } = useSparUIContext();

  const onConnect = (uri: string) => {
    sparAPIClient.authorizeAgentOAuth({ uri });
  };

  return (
    <Box display="flex" flexDirection="column" gap="$16" mb="$16">
      {oAuthState.map(({ providerType, isAuthorized, uri }) => {
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
                  {isConfigured ? 'Connect' : 'Configure'} {providerType}
                </Typography>
                <Typography color="content.subtle">
                  Review the permissions this agent needs and approce access.
                </Typography>
              </Box>
            </Box>
            <Box ml="auto" alignSelf="center">
              <Button type="button" round onClick={() => onConnect(uri)}>
                Connect
              </Button>
            </Box>
          </Box>
        );
      })}
    </Box>
  );
};
