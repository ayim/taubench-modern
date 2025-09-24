import { Box, Typography } from '@sema4ai/components';
import React from 'react';

export const DescriptionSection = ({ description }: { description: string }) => {
  return (
    <Box display="flex" flexDirection="column" gap="$4">
      <Typography variant="body-medium" fontWeight="bold">
        Description
      </Typography>
      <Typography variant="body-medium">{description}</Typography>
    </Box>
  );
};
