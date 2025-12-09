import { FC } from 'react';
import { Box, Typography } from '@sema4ai/components';
import { IconInformation } from '@sema4ai/icons';

interface Props {
  reason?: string;
}

export const ConversationDisabledMessage: FC<Props> = ({ reason }) => (
  <Box display="flex" flexDirection="column" gap="$16" mb="$16">
    <Box
      display="flex"
      flexDirection={['column', 'column', 'row', 'row']}
      gap="$20"
      borderRadius="$20"
      p="$20"
      backgroundColor="background.subtle"
      boxShadow="small"
    >
      <Box display="flex" gap="$16">
        <IconInformation size={32} />
        <Box>
          <Typography variant="body-large" mb="$4" fontWeight="medium">
            Chat disabled
          </Typography>
          <Typography color="content.subtle">
            {reason || 'Agent conversations are disabled due to an unknown error.'}
          </Typography>
        </Box>
      </Box>
    </Box>
  </Box>
);
