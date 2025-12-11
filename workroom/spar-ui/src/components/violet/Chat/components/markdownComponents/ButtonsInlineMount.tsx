import { FC } from 'react';
import { Box, ListSkeleton, SkeletonLoader, Typography } from '@sema4ai/components';
import { QuickOptions, QuickOptionsPayload } from '../interactionComponents/QuickOptions';

export type ButtonAction = {
  title?: string;
  message?: string;
  iconName?: string;
  primary?: boolean;
  label?: string;
  value?: string;
  icon?: string | null;
};

type Props = {
  status: string;
  description?: string;
  error?: string | null;
  thinking?: string;
  actions: ButtonAction[];
  messageId?: string;
};

export const ButtonsInlineMount: FC<Props> = ({ status, description, error, thinking, actions, messageId = '' }) => {
  const lowerStatus = (status || '').toLowerCase();

  const payload: QuickOptionsPayload = {
    type: 'quick-options',
    data: actions.map((a) => ({
      title: a.title || a.label || '',
      message: a.message || a.value || '',
      iconName: a.iconName || (a.icon as string | undefined),
      primary: a.primary ?? false,
    })),
  };

  const isDone = lowerStatus === 'done';
  const loadingCopy = thinking || description;

  if (lowerStatus === 'error') {
    return (
      <Box padding="$3" borderRadius="$3" backgroundColor="background.subtle">
        {description ? (
          <Typography variant="body-small" color="content.primary" marginBottom="$2">
            {description}
          </Typography>
        ) : null}
        <Typography variant="body-small" color="content.error">
          {error || 'Failed to generate buttons.'}
        </Typography>
      </Box>
    );
  }

  if (!isDone) {
    return (
      <Box
        padding="$3"
        borderRadius="$3"
        style={{ border: '1px solid rgba(0,0,0,0.05)', maxWidth: '320px' }}
        backgroundColor="background.subtle"
        display="flex"
        flexDirection="column"
        gap="$2"
      >
        {loadingCopy ? (
          <Typography variant="body-small" color="content.subtle">
            {loadingCopy}
          </Typography>
        ) : null}
        <SkeletonLoader skeleton={ListSkeleton} loading />
      </Box>
    );
  }

  return (
    <Box display="flex" flexDirection="column" gap="$2">
      {description ? (
        <Typography variant="body-small" color="content.subtle">
          {description}
        </Typography>
      ) : null}
      <QuickOptions payload={payload} messageId={messageId} />
    </Box>
  );
};
