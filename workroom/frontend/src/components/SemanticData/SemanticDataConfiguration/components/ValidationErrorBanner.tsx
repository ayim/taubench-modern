import { FC } from 'react';
import { Banner, Box } from '@sema4ai/components';
import { IconInformation } from '@sema4ai/icons';

type Props = {
  errors: string[];
};

export const ValidationErrorBanner: FC<Props> = ({ errors }) => {
  if (errors.length === 0) {
    return null;
  }

  return (
    <Banner
      message="Semantic Data Model Validation Errors"
      variant="error"
      icon={IconInformation}
      description={
        <Box as="span" display="block" maxHeight={150} overflow="auto" style={{ whiteSpace: 'pre-line' }}>
          {errors.map((error) => `• ${error}`).join('\n')}
        </Box>
      }
    />
  );
};
