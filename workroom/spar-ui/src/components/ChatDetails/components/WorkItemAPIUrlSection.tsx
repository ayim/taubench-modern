import { Box, Input, Typography, useClipboard, useSnackbar } from '@sema4ai/components';
import { IconCheck2, IconCopy } from '@sema4ai/icons';
import { useEffect } from 'react';
import { useWorkItemAPIUrlQuery } from '../../../queries/workItemAPI';

export const WorkItemAPIUrlSection = () => {
  const { onCopyToClipboard, copiedToClipboard } = useClipboard();
  const { addSnackbar } = useSnackbar();
  const { data: workItemApiUrl } = useWorkItemAPIUrlQuery({});

  useEffect(() => {
    if (copiedToClipboard) {
      addSnackbar({
        message: 'Copied to clipboard',
        variant: 'success',
      });
    }
  }, [copiedToClipboard]);

  if (!workItemApiUrl) {
    return null;
  }

  return (
    <Box as="section">
      <Typography variant="body-medium" fontWeight="bold" marginBottom="$4">
        Work Item API URL
      </Typography>

      <Input
        value={workItemApiUrl}
        readOnly
        iconRight={copiedToClipboard ? IconCheck2 : IconCopy}
        onIconRightClick={onCopyToClipboard(workItemApiUrl)}
        iconRightLabel="Copy URL"
        aria-label="workItem-api-url"
      />
    </Box>
  );
};
