import { FC, useMemo } from 'react';
import { Badge, Box, Tooltip, Typography } from '@sema4ai/components';
import { IconInformation } from '@sema4ai/icons';
import { keyframes, styled } from '@sema4ai/theme';

type InlineWidget = {
  id?: string;
  kind?: string;
  description?: string;
  status?: string;
  thinking?: string;
  error?: string | null;
};

const statusVariant = (status?: string): React.ComponentProps<typeof Badge>['variant'] => {
  switch ((status || '').toLowerCase()) {
    case 'done':
      return 'success';
    case 'generating':
    case 'detected':
      return 'info';
    case 'error':
      return 'danger';
    default:
      return 'secondary';
  }
};

const thinkingPreview = (thinking?: string) => {
  if (!thinking) return '';
  const trimmed = thinking.trim();
  if (trimmed.length <= 160) return trimmed;
  return `${trimmed.slice(-160)}…`;
};

const spin = keyframes`
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
`;

export const Spinner = styled('span')`
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid ${({ theme }) => theme.colors.border.subtle.color};
  border-top-color: ${({ theme }) => theme.colors.border.primary.color};
  border-radius: 50%;
  animation: ${spin} 0.8s linear infinite;
`;

export const InlineWidgets: FC<{ widgets: InlineWidget[] }> = ({ widgets }) => {
  const items = useMemo(
    () =>
      widgets
        .filter((w) => (w.status || '').toLowerCase() !== 'done') // hide completed widgets
        .map((w) => ({
          id: w.id ?? w.description ?? w.kind ?? Math.random().toString(36).slice(2),
          description: w.description ?? 'Inline widget',
          status: w.status ?? 'detected',
          thinking: w.thinking,
          error: w.error,
        })),
    [widgets],
  );

  if (items.length === 0) return null;

  return (
    <Box display="flex" flexDirection="column" gap="$2" paddingTop="$4">
      {items.map((item) => {
        const preview = thinkingPreview(item.thinking);
        const tooltip = item.error ?? preview;
        return (
          <Box
            key={item.id}
            display="flex"
            alignItems="center"
            gap="$3"
            padding="$3"
            borderRadius="$2"
            backgroundColor="background.subtle"
          >
            <Spinner aria-label="Loading widget" />
            <Box display="flex" flexDirection="column" flex={1} minWidth={0}>
              <Typography variant="body-small" color="content.subtle">
                {item.description}
              </Typography>
              <Box display="flex" alignItems="center" gap="$2" marginTop="$1">
                <Badge size="small" variant={statusVariant(item.status)} label={item.status || 'loading'} />
                {tooltip ? (
                  <Tooltip text={tooltip} placement="left">
                    <IconInformation size={16} color="content.subtle" />
                  </Tooltip>
                ) : null}
              </Box>
            </Box>
          </Box>
        );
      })}
    </Box>
  );
};
