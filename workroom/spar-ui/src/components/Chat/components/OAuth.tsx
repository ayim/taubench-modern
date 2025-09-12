import { FC } from 'react';
import { Box, Button } from '@sema4ai/components';
import { IconCheckmark } from '@sema4ai/icons';
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
    <Box display="flex" flexDirection="column" borderRadius="$24" p="$12" borderColor="border.subtle" boxShadow="small">
      {oAuthState.map(({ providerType, isAuthorized, uri }) => {
        const ProviderIcon = oAuthProviderIcons[providerType];

        return (
          <div key={providerType}>
            <div>
              <ProviderIcon size="$48" />
            </div>
            <Box>
              {isAuthorized ? (
                <IconCheckmark size={32} />
              ) : (
                <Button type="button" onClick={() => onConnect(uri)}>
                  Connect
                </Button>
              )}
            </Box>
          </div>
        );
      })}
    </Box>
  );
};
