import { FC, useMemo } from 'react';
import { Box, Button, Dialog, Link, Progress, Typography } from '@sema4ai/components';
import { OAuthProvider } from '@sema4ai/oauth-client';
import { AgentIcon, PackageCard } from '@sema4ai/layouts';
import { IconArrowUpRight, IconInformation } from '@sema4ai/icons';

import { useParams } from '../../../../../../hooks';
import { useAgentActionPackagesQuery } from '../../../../../../queries/actions';
import { isOAuthSecret } from '../../../../../../lib/DeprecatedTypes';
import { snakeCaseToTitleCase } from '../../../../../../common/helpers';
import { EXTERNAL_LINKS } from '../../../../../../lib/constants';

type Props = {
  provider: OAuthProvider;
  scopes: string[];
  onClose: () => void;
};

export const DetailsDialog: FC<Props> = ({ onClose, scopes, provider }) => {
  const { agentId } = useParams('/thread/$agentId/$threadId');

  const { data: allActionPackages, isLoading } = useAgentActionPackagesQuery({ agentId });

  const actionPackages = useMemo(() => {
    return allActionPackages?.filter(
      ({ metadata }) =>
        metadata.settings.filter(isOAuthSecret).findIndex((setting) => setting.provider === provider) > -1,
    );
  }, [allActionPackages]);

  const providerTitle = snakeCaseToTitleCase(provider);

  if (isLoading) {
    return <Progress variant="page" />;
  }

  return (
    <Dialog open onClose={onClose} width={680}>
      <Dialog.Header>
        <Dialog.Header.Title title={`Why ${providerTitle}`} />
        <Dialog.Header.Description>
          {actionPackages
            ? `All Actions you need to work with ${providerTitle}`
            : `Required OAuth scopes for ${providerTitle}`}
        </Dialog.Header.Description>
      </Dialog.Header>
      <Dialog.Content>
        {actionPackages ? (
          actionPackages.map(({ name, metadata }) => (
            <PackageCard
              icon={<AgentIcon size="m" variant="brand-secondary" />}
              title={name}
              version=""
              description={metadata.description}
              actions={metadata.settings
                .map((setting) => {
                  if (!isOAuthSecret(setting)) {
                    return null;
                  }

                  const action = metadata.actions.find((curr) => curr.name === setting.actionName);

                  if (!action) {
                    return null;
                  }

                  return action.friendlyName;
                })
                .filter((curr) => curr !== null)}
              isOpen
            />
          ))
        ) : (
          <>
            {scopes.map((scope) => (
              <Box key={scope} mb="$8">
                <Typography variant="body-medium">{scope}</Typography>
              </Box>
            ))}
          </>
        )}
      </Dialog.Content>
      <Dialog.Actions>
        <Button variant="secondary" onClick={onClose} round>
          Close
        </Button>
        <Box mr="auto" display="flex" gap="$8">
          <Link
            icon={IconInformation}
            iconAfter={IconArrowUpRight}
            href={EXTERNAL_LINKS.ACTIONS_AUTHENTICATION_HELP}
            variant="subtle"
            target="_blank"
          >
            Read Documentation
          </Link>
          <Link
            iconAfter={IconArrowUpRight}
            href={EXTERNAL_LINKS.ACTIONS_PRIVACY_POLICY}
            variant="subtle"
            target="_blank"
          >
            Privacy Policy
          </Link>
        </Box>
      </Dialog.Actions>
    </Dialog>
  );
};
