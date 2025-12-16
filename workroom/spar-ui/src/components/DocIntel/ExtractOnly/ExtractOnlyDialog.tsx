import { FC, useEffect, useCallback, useState, useRef, useMemo } from 'react';
import { Box, Dialog, Typography, Switch, Button, Steps, Divider, Tooltip } from '@sema4ai/components';
import { IconPencil, IconCheckCircle, IconRefresh, IconStatusIdle, IconStatusEnabled } from '@sema4ai/icons';
import { ConfigurationPanel, ConfigurationPanelRef } from './ConfigurationPanel';
import { ExtractResultsPanel } from './ExtractResultsPanel';
import { DocumentViewer } from '../shared/components/DocumentViewer';
import { useResizablePanel, useResultsSelection } from '../shared/hooks';
import { extractedDataToBlocks } from '../shared/utils';
import type { ExtractSchemaResponse, ExtractResponse } from '../shared/types';
import { usePdfAnnotations } from '../shared/hooks/usePdfAnnotations';
import { useExtractDialogState } from './hooks/useExtractDialogState';
import { RegenerateFileSchemaDialog } from '../shared/components/RegenerateFileSchemaDialog';
import { useMessageStream } from '../../../hooks/useMessageStream';

type ValidJSON = unknown;
interface SendResultsToThreadProps {
  results: ValidJSON;
  agentId: string;
  threadId: string;
  fileName: string;
}

const getStringResults = (results: ValidJSON) => {
  try {
    return JSON.stringify(results);
  } catch (error) {
    return String(results);
  }
};

const useSendResultsToThread = ({ results, agentId, threadId, fileName }: SendResultsToThreadProps) => {
  const { sendMessage } = useMessageStream({
    agentId,
    threadId,
  });

  const sendResultsToThread = useCallback(async () => {
    return sendMessage(
      `The following results were extracted from ${fileName}:
      \`\`\`${getStringResults(results)}\`\`\`
      `,
      [],
    );
  }, [results, fileName, sendMessage]);

  return useMemo(() => {
    if (!results) return { sendResultsToThread: () => Promise.resolve(), enabled: false };
    return { sendResultsToThread, enabled: true };
  }, [sendResultsToThread, results]);
};

/**
 * Dialog for extracting structured data from documents without saving to database.
 * Supports two modes:
 * - Thread mode: Edit existing extraction from conversation
 * - Standalone: Generate schema and extract fresh data
 */
interface ExtractOnlyDialogProps {
  isOpen: boolean;
  onClose: () => void;
  file: File;
  agentId: string;
  threadId: string;
  schema?: ExtractSchemaResponse;
  extractResult?: ExtractResponse;
}

export const ExtractOnlyDialog: FC<ExtractOnlyDialogProps> = ({
  isOpen,
  onClose,
  file,
  agentId,
  threadId,
  schema,
  extractResult,
}) => {
  const configPanelRef = useRef<ConfigurationPanelRef>(null);
  const [showRawJson, setShowRawJson] = useState(false);
  const [activeTab, setActiveTab] = useState<number>(0);
  const [openExitConfirmation, setOpenExitConfirmation] = useState(false);
  const { panelWidth, handleMouseDown, minPanelWidth } = useResizablePanel();
  const [openRetryExtract, setOpenRetryExtract] = useState(false);

  // Annotation mode state
  const [isAnnotating, setIsAnnotating] = useState(false);

  const {
    showAnnotationPopup,
    pendingAnnotation,
    saveTextSelectionAsField,
    cancelTextSelection,
    createTextSelectionAnnotation,
  } = usePdfAnnotations();

  const {
    extractResult: extractResultData,
    currentSchema,
    hasChanges,
    extractRevision,
    extractedDataWithCitations,
    isGeneratingSchema,
    isExtracting,
    isFetchingCachedSchema,
    error,
    hasInitialized,
    handleGenerateSchema,
    handleFetchCachedSchema,
    handleExtract,
    handleReExtract,
    handleSchemaChange,
    initializeFromExisting,
    setHasChanges,
  } = useExtractDialogState({
    agentId,
    threadId,
    file,
    schema,
    extractResult,
  });

  const isResultsStepDisabled = isFetchingCachedSchema || isGeneratingSchema || isExtracting;

  const handleTabChange = useCallback(
    (newTab: number) => {
      if (newTab === 1 && isResultsStepDisabled) {
        return;
      }
      setActiveTab(newTab);
    },
    [isResultsStepDisabled],
  );

  const canReExtract = useMemo(
    () => hasChanges && !!currentSchema && !isGeneratingSchema && !isExtracting,
    [hasChanges, currentSchema, isGeneratingSchema, isExtracting],
  );

  // Transform extracted data to blocks for Results tab
  const extractedBlocks = useMemo(() => {
    if (!extractResultData) return [];
    return extractedDataToBlocks(extractResultData);
  }, [extractResultData]);

  // Bidirectional selection between PDF and Results
  const { selectedBlockId, selectedFieldId, handlePdfFieldClick, handleBlockClick } = useResultsSelection({
    blocks: extractedBlocks,
  });

  // Render content based on active tab
  const renderTabContent = () => {
    if (activeTab === 0) {
      return (
        <ConfigurationPanel
          ref={configPanelRef}
          currentSchema={currentSchema}
          extractResultData={extractResultData}
          showRawJson={showRawJson}
          isGeneratingSchema={isGeneratingSchema}
          isExtracting={isExtracting}
          error={error}
          onReExtract={handleReExtract}
          onSchemaChange={handleSchemaChange}
          onHasChanges={setHasChanges}
        />
      );
    }

    return (
      <ExtractResultsPanel
        currentSchema={currentSchema}
        extractResult={extractResultData}
        extractedBlocks={extractedBlocks}
        isGeneratingSchema={isGeneratingSchema}
        isExtracting={isExtracting}
        error={error}
        showRawJson={showRawJson}
        selectedBlockId={selectedBlockId}
        onBlockClick={handleBlockClick}
      />
    );
  };

  const handleClose = useCallback(() => {
    if (hasChanges) {
      setOpenExitConfirmation(true);
    } else {
      onClose();
    }
  }, [hasChanges, onClose]);

  const handleConfirmClose = useCallback(() => {
    setOpenExitConfirmation(false);
    onClose();
  }, [onClose]);

  const handleAnnotationCreate = useCallback(
    (selection: {
      pageNumber: number;
      left: number;
      top: number;
      width: number;
      height: number;
      selectedText: string;
    }) => {
      createTextSelectionAnnotation(selection);
    },
    [createTextSelectionAnnotation],
  );

  const handleSaveAnnotationField = useCallback(
    (userDescription: string, userFieldName: string) => {
      if (!currentSchema) return;

      // Sanitize the user's field name input
      const fieldName = userFieldName
        .toLowerCase()
        .replace(/[^\w\s]/g, '')
        .replace(/\s+/g, '_')
        .replace(/_+/g, '_')
        .replace(/^_|_$/g, '');

      // Add field to schema
      const updatedProperties = {
        ...currentSchema.properties,
        [fieldName]: {
          type: 'string',
          description: userDescription, // User's typed instruction
        },
      };

      const updatedSchema = {
        ...currentSchema,
        properties: updatedProperties,
      };

      handleSchemaChange(updatedSchema);
      setHasChanges(true);
      saveTextSelectionAsField(userDescription, userFieldName);
      setIsAnnotating(false);
    },
    [currentSchema, saveTextSelectionAsField, handleSchemaChange, setHasChanges],
  );

  // Prevent escape key from closing the dialog
  useEffect(() => {
    if (!isOpen) {
      return () => {
        // No-op cleanup when dialog is closed
      };
    }

    const handleEscapeKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();
      }
    };

    document.addEventListener('keydown', handleEscapeKey, true);

    return () => {
      document.removeEventListener('keydown', handleEscapeKey, true);
    };
  }, [isOpen]);

  const handleGenerateSchemaAndExtract = useCallback(
    async (...args: Parameters<typeof handleGenerateSchema>) =>
      handleGenerateSchema(...args).then((schemaResponse) => {
        if (schemaResponse) {
          hasInitialized.current = true;
          return handleExtract(schemaResponse);
        }
        return null;
      }),
    [handleGenerateSchema, handleExtract],
  );

  // Initialize data once on mount: check for cached schema, or generate fresh
  useEffect(() => {
    if (hasInitialized.current) {
      return;
    }

    if (schema && extractResult) {
      initializeFromExisting(schema, extractResult);
      hasInitialized.current = true;
      return;
    }

    if (file && !currentSchema && !isGeneratingSchema && !isFetchingCachedSchema) {
      // First try to fetch a cached schema from the server
      handleFetchCachedSchema().then((cachedSchema) => {
        if (cachedSchema) {
          // Cached schema found, use it and run extraction
          hasInitialized.current = true;
          handleExtract(cachedSchema);
        } else {
          // No cached schema, generate a new one
          handleGenerateSchemaAndExtract();
        }
      });
    }
  }, [
    file,
    currentSchema,
    schema,
    extractResult,
    isGeneratingSchema,
    isFetchingCachedSchema,
    handleFetchCachedSchema,
    handleExtract,
    handleGenerateSchemaAndExtract,
    initializeFromExisting,
  ]);

  const { sendResultsToThread, enabled: sendingResultsEnabled } = useSendResultsToThread({
    results: extractResultData?.result,
    agentId,
    threadId,
    fileName: file.name,
  });
  const shouldAllowRegenerating = activeTab === 0 && !isResultsStepDisabled;
  const shouldAllowSendingToThread = activeTab === 1 && !isExtracting && sendingResultsEnabled;

  const onShowResultsInThread = useCallback(() => {
    if (sendingResultsEnabled) {
      sendResultsToThread().then(onClose);
    }
  }, [sendResultsToThread]);

  return (
    <>
      <Dialog open={isOpen} onClose={handleClose} size="full-screen">
        <Dialog.Header>
          <Box display="flex" alignItems="center" gap="$8">
            <Typography fontSize="$20" fontWeight="bold">
              Extract Data from Document
            </Typography>
            <Typography fontSize="$20" fontWeight="bold" style={{ color: 'gray' }}>
              {file.name}
            </Typography>
          </Box>
        </Dialog.Header>

        <Dialog.Content>
          <Box display="flex" gap="$16" flex="1" height="100%" width="100%" maxWidth="100%" overflow="scroll">
            <Box display="flex" flexDirection="column" flex="1" height="100%" minWidth="600px">
              {/* Temporarily disabled: onAnnotateToggle prop removed */}
              <DocumentViewer
                key={`extract-${extractRevision}`}
                file={file}
                extractedData={extractedDataWithCitations}
                isAnnotating={isAnnotating}
                selectedFieldId={selectedFieldId}
                onFieldClick={handlePdfFieldClick}
                onAnnotationCreate={handleAnnotationCreate}
                showAnnotationPopup={showAnnotationPopup}
                pendingAnnotation={pendingAnnotation}
                onSaveAnnotation={handleSaveAnnotationField}
                onCancelAnnotation={() => {
                  cancelTextSelection();
                  // Keep annotation mode active - only close the popup
                }}
              />
            </Box>

            <Box
              display="flex"
              style={{ width: `${panelWidth}px`, position: 'relative' }}
              minWidth={`${minPanelWidth}px`}
              height="100%"
            >
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

              <Box
                width="100%"
                minWidth="600px"
                height="100%"
                display="flex"
                flexDirection="column"
                minHeight="0"
                borderWidth="1px"
                borderRadius="$8"
                borderColor="border.subtle"
                flex="1"
              >
                <Box p="$24" width="50%" margin="0 auto">
                  <Steps activeStep={activeTab} setActiveStep={handleTabChange} size="large">
                    <Steps.Step stepIcon={IconPencil}>
                      <Typography fontSize="$14" fontWeight="medium">
                        Configuration
                      </Typography>
                    </Steps.Step>
                    <Steps.Step stepIcon={IconCheckCircle} disabled={isResultsStepDisabled}>
                      <Typography fontSize="$14" fontWeight="medium">
                        Results
                      </Typography>
                    </Steps.Step>
                  </Steps>
                </Box>
                <Divider />

                {/* RESULTS CONTENT */}
                <Box flex="1" overflow="hidden" minHeight="0" display="flex" flexDirection="column">
                  {renderTabContent()}
                </Box>

                <Box
                  padding="$8"
                  backgroundColor="background.primary"
                  flexShrink="0"
                  display="flex"
                  alignItems="center"
                  justifyContent="space-between"
                  gap="$16"
                  style={{ borderTop: '1px solid var(--sema4ai-colors-border-subtle)' }}
                >
                  <Box display="flex" alignItems="center" gap="$16">
                    <Switch
                      aria-labelledby="show-raw-json"
                      checked={showRawJson}
                      onChange={(e) => setShowRawJson(e.target.checked)}
                      disabled={isResultsStepDisabled}
                    />
                    <Typography>View as JSON</Typography>

                    {activeTab === 0 && (
                      <Tooltip
                        text={
                          hasChanges
                            ? 'Configuration changes made. Click Re-Run Extract to update extraction.'
                            : 'Configuration is up to date'
                        }
                      >
                        <Box display="flex" alignItems="center" gap="$4">
                          {hasChanges ? (
                            <>
                              <IconStatusIdle color="background.notification" size={24} />
                              <Typography fontSize="$14" color="content.subtle">
                                Changes pending
                              </Typography>
                            </>
                          ) : (
                            <>
                              <IconStatusEnabled color="content.success" size={24} />
                              <IconCheckCircle color="content.success" size={24} />
                            </>
                          )}
                        </Box>
                      </Tooltip>
                    )}
                  </Box>

                  <Box display="flex" alignItems="center" gap="$8">
                    {activeTab === 0 && hasChanges && (
                      <Button
                        variant="primary"
                        round
                        onClick={() => configPanelRef.current?.triggerReExtract()}
                        disabled={!canReExtract}
                        icon={IconRefresh}
                        loading={isExtracting}
                      >
                        Re-Run Extract
                      </Button>
                    )}
                    {shouldAllowRegenerating && (
                      <Button variant="outline" onClick={() => setOpenRetryExtract(true)} round>
                        Regenerate
                      </Button>
                    )}
                    {shouldAllowSendingToThread && (
                      <Button variant="primary" onClick={onShowResultsInThread} round>
                        Use in Conversation
                      </Button>
                    )}
                    <Button variant="secondary" onClick={handleClose} round>
                      Close
                    </Button>
                  </Box>
                </Box>
              </Box>
            </Box>
          </Box>
        </Dialog.Content>
      </Dialog>

      <RegenerateFileSchemaDialog
        open={openRetryExtract}
        onClose={() => setOpenRetryExtract(false)}
        fileName={file.name}
        threadId={threadId}
        agentId={agentId}
        onGenerateSchema={handleGenerateSchemaAndExtract}
        isGeneratingSchema={isGeneratingSchema}
        isExtracting={isExtracting}
      />

      <Dialog open={openExitConfirmation} onClose={() => setOpenExitConfirmation(false)} size="medium">
        <Dialog.Header>
          <Dialog.Header.Title title="Are you sure?" />
        </Dialog.Header>
        <Dialog.Content>
          You have unsaved changes to the extraction configuration. If you close now, these changes will be lost.
        </Dialog.Content>
        <Dialog.Actions>
          <Button variant="primary" onClick={handleConfirmClose}>
            Yes, close
          </Button>
          <Button variant="secondary" onClick={() => setOpenExitConfirmation(false)}>
            No, continue editing
          </Button>
        </Dialog.Actions>
      </Dialog>
    </>
  );
};
