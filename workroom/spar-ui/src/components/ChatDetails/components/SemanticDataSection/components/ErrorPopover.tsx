import { FC } from 'react';
import { Box, Typography, usePopover } from '@sema4ai/components';
import { IconStatusDisabled, IconStatusError } from '@sema4ai/icons';

type Props = {
  level: 'error' | 'warning';
  title: string;
  description: string;
  action: React.ReactNode;
  dataConnectionId?: string;
};

export const ErrorPopover: FC<Props> = ({ title, description, action, level }) => {
  const { referenceRef, referenceProps, PopoverContent, setOpen } = usePopover({
    hover: true,
    placement: 'top',
  });

  const onPopoverClick = () => {
    setOpen(false);
  };

  const Icon = level === 'error' ? IconStatusError : IconStatusDisabled;
  const iconColor = level === 'error' ? 'content.error' : 'background.notification';

  return (
    <Box display="flex" alignItems="center" onClick={onPopoverClick}>
      <Icon ref={referenceRef} {...referenceProps} color={iconColor} />
      <PopoverContent>
        <Box
          display="flex"
          gap="$12"
          flexDirection="column"
          width={260}
          p="$16"
          borderRadius="$12"
          boxShadow="medium"
          backgroundColor="background.panels"
        >
          <Box display="flex" alignItems="center" gap="$8">
            <Icon color={iconColor} />
            <Typography variant="body-large" fontWeight="medium">
              {title}
            </Typography>
          </Box>
          <Typography color="content.subtle.light" pb="$12">
            {description}
          </Typography>
          {action}
        </Box>
      </PopoverContent>
    </Box>
  );
};
