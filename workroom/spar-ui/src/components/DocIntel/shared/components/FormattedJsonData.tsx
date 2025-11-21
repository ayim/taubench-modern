import { FC, useMemo, useCallback } from 'react';
import { Box, Button, Tooltip, useClipboard, useSnackbar } from '@sema4ai/components';
import { IconDownload, IconCopy, IconCheck2 } from '@sema4ai/icons';
import { Code } from '../../../../common/code';

/**
 * FormattedJsonData - Displays data as formatted JSON with copy/download functionality
 * Generic component used across DocIntel flows (Parse Only, Extract, etc.)
 */

interface FormattedJsonDataProps {
  /** The data to display as JSON */
  data: unknown;
  /** Optional filename for download (defaults to 'extraction_data.json') */
  downloadFileName?: string;
  /** Optional aria label for accessibility */
  ariaLabel?: string;
}

export const FormattedJsonData: FC<FormattedJsonDataProps> = ({
  data,
  downloadFileName = 'extraction_data.json',
  ariaLabel = 'extraction-data-json',
}) => {
  const { onCopyToClipboard, copiedToClipboard } = useClipboard();
  const { addSnackbar } = useSnackbar();

  // Convert data to formatted JSON string
  const jsonString = useMemo(() => {
    return JSON.stringify(data, null, 2);
  }, [data]);

  // Function to download the data
  const handleDownload = useCallback(() => {
    const blob = new Blob([jsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = downloadFileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }, [jsonString, downloadFileName]);

  // Handle copy with snackbar notification
  const handleCopy = useCallback(() => {
    const copyHandler = onCopyToClipboard(jsonString);
    copyHandler();
    addSnackbar({ message: 'JSON copied to clipboard', variant: 'success' });
  }, [jsonString, onCopyToClipboard, addSnackbar]);

  // Create custom toolbar with copy and download buttons
  const customToolbar = useMemo(() => {
    return (
      <Box display="flex" justifyContent="flex-end" gap="$4" marginBottom="$4" marginTop="$4" marginRight="$8">
        <Tooltip text="Download JSON">
          <Button
            aria-label="Download JSON"
            variant="inverted"
            round
            icon={IconDownload}
            onClick={handleDownload}
            size="small"
          />
        </Tooltip>
        <Tooltip text="Copy JSON to clipboard">
          <Button
            aria-label="Copy JSON to clipboard"
            variant="inverted"
            round
            icon={copiedToClipboard ? IconCheck2 : IconCopy}
            onClick={handleCopy}
            size="small"
          />
        </Tooltip>
      </Box>
    );
  }, [copiedToClipboard, handleCopy, handleDownload]);

  return (
    <Box display="flex" flexDirection="column" height="100%" padding="$16">
      <Box flex="1" minHeight="300px" overflow="auto">
        <Code
          lang="json"
          value={jsonString}
          aria-labelledby={ariaLabel}
          readOnly
          theme="dark"
          lineNumbers
          toolbar={customToolbar}
        />
      </Box>
    </Box>
  );
};
