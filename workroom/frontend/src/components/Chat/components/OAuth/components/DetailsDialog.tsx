import { FC } from 'react';
import { Box, Button, Dialog, Link, Typography } from '@sema4ai/components';
import { OAuthProvider } from '@sema4ai/oauth-client';
import { IconArrowUpRight, IconInformation } from '@sema4ai/icons';

import { snakeCaseToTitleCase } from '~/components/helpers';
import { EXTERNAL_LINKS } from '../../../../../lib/constants';

type Props = {
  provider: OAuthProvider;
  scopes: string[];
  onClose: () => void;
};

export const DetailsDialog: FC<Props> = ({ onClose, scopes, provider }) => {
  const providerTitle = snakeCaseToTitleCase(provider);

  return (
    <Dialog open onClose={onClose} width={680}>
      <Dialog.Header>
        <Dialog.Header.Title title={`Why ${providerTitle}`} />
        <Dialog.Header.Description>Required OAuth scopes for</Dialog.Header.Description>
      </Dialog.Header>
      <Dialog.Content>
        {scopes.map((scope) => (
          <Box key={scope} mb="$8">
            <Typography variant="body-medium">{scope}</Typography>
          </Box>
        ))}
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
