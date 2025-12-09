import { FC, useMemo, useCallback } from 'react';
import { Box, Button, Tooltip, useClipboard, useSnackbar } from '@sema4ai/components';
import { IconDownload, IconCopy, IconCheck2 } from '@sema4ai/icons';
import { Code } from '../../../../../common/code';
import { EXTRACTION_FILE_NAMES, EXTRACTION_ARIA_LABELS } from '../constants/extractionFiles';

/**
 * FormattedJsonData - Displays data as formatted JSON with copy/download functionality
 * Generic component used across DocIntel flows (Parse Only, Extract, etc.)
 */

type JsonDataVariant = 'extraction-schema' | 'extraction-data' | 'parse-results';

interface FormattedJsonDataProps {
  /** The data to display as JSON */
  data: unknown;
  /** Variant that determines file name and aria label (overrides downloadFileName/ariaLabel if provided) */
  variant?: JsonDataVariant;
  /** Optional filename for download (used if variant is not provided, defaults to 'extraction_data.json') */
  downloadFileName?: string;
  /** Optional aria label for accessibility (used if variant is not provided, defaults to 'extraction-data-json') */
  ariaLabel?: string;
}

const VARIANT_CONFIG: Record<JsonDataVariant, { fileName: string; ariaLabel: string }> = {
  'extraction-schema': {
    fileName: EXTRACTION_FILE_NAMES.SCHEMA,
    ariaLabel: EXTRACTION_ARIA_LABELS.SCHEMA,
  },
  'extraction-data': {
    fileName: EXTRACTION_FILE_NAMES.DATA,
    ariaLabel: EXTRACTION_ARIA_LABELS.DATA,
  },
  'parse-results': {
    fileName: 'parse_results.json',
    ariaLabel: 'parse-results-json',
  },
};

export const FormattedJsonData: FC<FormattedJsonDataProps> = ({ data, variant, downloadFileName, ariaLabel }) => {
  // Determine file name and aria label based on variant or props
  const finalFileName = variant ? VARIANT_CONFIG[variant].fileName : (downloadFileName ?? 'extraction_data.json');
  const finalAriaLabel = variant ? VARIANT_CONFIG[variant].ariaLabel : (ariaLabel ?? 'extraction-data-json');
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
    link.download = finalFileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }, [jsonString, finalFileName]);

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
          aria-labelledby={finalAriaLabel}
          readOnly
          theme="dark"
          lineNumbers
          toolbar={customToolbar}
        />
      </Box>
    </Box>
  );
};
