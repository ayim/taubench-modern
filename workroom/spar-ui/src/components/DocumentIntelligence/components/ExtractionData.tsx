import { FC, memo, useMemo, useCallback } from 'react';
import { Box, Typography, Button, Tooltip, useClipboard, useSnackbar } from '@sema4ai/components';
import { IconSparkles2, IconDownload, IconCopy, IconCheck2 } from '@sema4ai/icons';
import { useDocumentIntelligenceStore } from '../store/useDocumentIntelligenceStore';
import { Code } from '../../../common/code';

export const ExtractionData: FC = memo(() => {
  const originalGeneratedSchema = useDocumentIntelligenceStore((state) => state.originalGeneratedSchema);
  const { onCopyToClipboard, copiedToClipboard } = useClipboard();
  const { addSnackbar } = useSnackbar();

  // Convert schema to downloadable JSON string
  const schemaJsonString = useMemo(() => {
    if (!originalGeneratedSchema) return null;
    return JSON.stringify(originalGeneratedSchema, null, 2);
  }, [originalGeneratedSchema]);

  // Display the original extraction schema as JSON string
  const jsonString = useMemo(() => {
    return schemaJsonString || '';
  }, [schemaJsonString]);

  // Function to download the schema
  const handleDownloadSchema = useCallback(() => {
    if (!schemaJsonString) return;

    const blob = new Blob([schemaJsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'extraction_schema.json';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }, [schemaJsonString]);

  // Handle copy with snackbar notification
  const handleCopy = useCallback(() => {
    const copyHandler = onCopyToClipboard(jsonString);
    copyHandler();
    addSnackbar({ message: 'JSON copied to clipboard', variant: 'success' });
  }, [jsonString, onCopyToClipboard, addSnackbar]);

  // Create custom toolbar with copy and menu buttons
  const customToolbar = useMemo(() => {
    return (
      <Box display="flex" justifyContent="flex-end" gap="$4" marginBottom="$4" marginTop="$4" marginRight="$8">
        {originalGeneratedSchema && (
          <Tooltip text="Download Extraction Schema">
            <Button
              aria-label="Download Extraction Schema"
              variant="inverted"
              round
              icon={IconDownload}
              onClick={handleDownloadSchema}
              size="small"
            />
          </Tooltip>
        )}
        <Tooltip text="Copy Extraction Schema to clipboard">
          <Button
            aria-label="Copy Extraction Schema to clipboard"
            variant="inverted"
            round
            icon={copiedToClipboard ? IconCheck2 : IconCopy}
            onClick={handleCopy}
            size="small"
          />
        </Tooltip>
      </Box>
    );
  }, [onCopyToClipboard, copiedToClipboard, originalGeneratedSchema, handleCopy, handleDownloadSchema]);

  return (
    <Box display="flex" flexDirection="column" height="100%" minHeight="400px">
      <Box display="flex" alignItems="center" gap="$8" marginBottom="$18">
        <IconSparkles2 color="content.subtle.light" />
        <Typography fontSize="$12" fontWeight="medium" color="content.subtle.light">
          Fields and tables inferred below.
        </Typography>
      </Box>
      <Box flex="1" minHeight="300px" overflow="auto">
        <Code
          lang="json"
          value={jsonString}
          aria-labelledby="extracted-data-json"
          readOnly
          theme="dark"
          lineNumbers
          toolbar={customToolbar}
        />
      </Box>
    </Box>
  );
});
