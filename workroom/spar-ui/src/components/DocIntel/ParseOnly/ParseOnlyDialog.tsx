import { FC, useEffect, useCallback, useState } from 'react';
import { Box, Dialog, Typography, useSnackbar, Switch, Button } from '@sema4ai/components';
import { ParseResultsPanel } from './ParseResultsPanel';
import { DocumentViewer } from '../shared/components/DocumentViewer';
import { useParseDocumentMutation } from '../../../queries/documentIntelligence';
import { useResizablePanel } from '../shared/hooks/useResizablePanel';
import type { ServerResponse } from '../../../queries/shared';

/**
 * ParseOnlyDialog - Dialog for Parse Only mode
 * Allows users to parse a document and view results without saving to database
 */

type ParseResult = ServerResponse<'post', '/api/v2/document-intelligence/documents/parse'>;

interface ParseOnlyDialogProps {
  isOpen: boolean;
  onClose: () => void;
  file: File;
  threadId: string;
}

export const ParseOnlyDialog: FC<ParseOnlyDialogProps> = ({ isOpen, onClose, file, threadId }) => {
  const { addSnackbar } = useSnackbar();
  const [parseResult, setParseResult] = useState<ParseResult | null>(null);
  const [showRawJson, setShowRawJson] = useState(false);
  const { panelWidth, handleMouseDown, minPanelWidth } = useResizablePanel();

  const { mutateAsync, isPending, error } = useParseDocumentMutation({});

  const handleParse = useCallback(async () => {
    try {
      const result = await mutateAsync({
        threadId,
        formData: file,
      });

      setParseResult(result);
    } catch (err) {
      addSnackbar({ message: (err as Error).message, variant: 'danger' });
    }
  }, [file, threadId, mutateAsync, addSnackbar]);

  useEffect(() => {
    if (file && !parseResult) {
      handleParse();
    }
  }, [file, parseResult, handleParse]);

  return (
    <Dialog open={isOpen} onClose={onClose} size="full-screen">
      <Dialog.Header>
        <Box display="flex" alignItems="center" gap="$8">
          <Typography fontSize="$20" fontWeight="bold">
            Parse Document
          </Typography>
          <Typography fontSize="$20" fontWeight="bold" style={{ color: 'gray' }}>
            {file.name}
          </Typography>
        </Box>
      </Dialog.Header>

      <Dialog.Content>
        <Box display="flex" gap="$16" flex="1" height="100%" width="100%" maxWidth="100%" overflow="scroll">
          {/* DOCUMENT VIEWER */}
          <Box display="flex" flexDirection="column" flex="1" height="100%" minWidth="600px">
            <DocumentViewer file={file} parseData={parseResult} />
          </Box>

          {/* RESULTS PANEL */}
          <Box
            display="flex"
            style={{ width: `${panelWidth}px`, position: 'relative' }}
            minWidth={`${minPanelWidth}px`}
            height="100%"
          >
            {/* Resize handle */}
            <Box
              style={{
                position: 'absolute',
                left: '-6px',
                top: '45%',
                width: '12px',
                height: '31px',
                background: '#c1c1c1',
                borderRadius: '4px',
                cursor: 'col-resize',
                zIndex: 20,
              }}
              onMouseDown={handleMouseDown}
            />

            {/* Results Content */}
            <Box
              width="100%"
              minWidth="600px"
              height="100%"
              display="flex"
              flexDirection="column"
              gap="$16"
              minHeight="0"
            >
              <Box
                borderWidth="1px"
                borderRadius="$8"
                borderColor="border.subtle"
                display="flex"
                flexDirection="column"
                flex="1"
                minHeight="0"
              >
                {/* RESULTS CONTENT */}
                <Box
                  flex="1"
                  overflow="auto"
                  minHeight="0"
                  style={{
                    scrollbarWidth: 'none',
                    msOverflowStyle: 'none',
                  }}
                >
                  <ParseResultsPanel parseResult={parseResult} isLoading={isPending} error={error?.message || null} />
                </Box>

                {/* FOOTER */}
                <Box
                  padding="$8"
                  backgroundColor="background.primary"
                  flexShrink="0"
                  style={{ borderTop: '1px solid var(--sema4ai-colors-border-subtle)' }}
                >
                  <Box display="flex" alignItems="center" justifyContent="space-between" gap="$16">
                    <Box display="flex" alignItems="center" gap="$16">
                      <Switch
                        aria-labelledby="show-raw-json"
                        checked={showRawJson}
                        onChange={(e) => setShowRawJson(e.target.checked)}
                        disabled={isPending}
                      />
                      <Typography>View as JSON</Typography>
                    </Box>
                    <Button variant="primary" onClick={onClose} round>
                      Close
                    </Button>
                  </Box>
                </Box>
              </Box>
            </Box>
          </Box>
        </Box>
      </Dialog.Content>
    </Dialog>
  );
};
