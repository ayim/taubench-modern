import { FC, ReactNode } from 'react';
import { Box, Typography } from '@sema4ai/components';
import type { IconType } from '@sema4ai/icons';

type Props = {
  children: ReactNode;
  title: string;
  icon?: IconType;
  actions?: ReactNode;
};

export const Page: FC<Props> = ({ actions, children, title, icon: Icon }) => {
  return (
    <Box as="section" py="$64" px={['$16', '$16', '$16', '$40']} maxWidth={1280} width="100%" mx="auto">
      <Box display="flex" justifyContent="space-between" alignItems="center" mb="$20">
        <Box display="flex" gap="$16">
          {Icon && <Icon size={36} />}
          <Typography variant="display-large">{title}</Typography>
        </Box>
        {actions}
      </Box>
      {children}
    </Box>
  );
};
