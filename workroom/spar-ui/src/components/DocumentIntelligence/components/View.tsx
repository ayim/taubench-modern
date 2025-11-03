import { FC, useState, useCallback } from 'react';
import { IconAlert, IconRefresh } from '@sema4ai/icons';
import { Box, Switch, Snackbar, Divider, Typography, Banner, Button, useSnackbar } from '@sema4ai/components';
import { StepType, DocumentData } from '../types';
import { DataModelNameDialog } from './common/DataModelNameDialog';
import { useDocumentIntelligenceStore } from '../store/useDocumentIntelligenceStore';
import {
  useDataModelNameDialogSave,
  useStepNavigation,
  useResizablePanel,
  useFlowHandlers,
} from '../hooks/useDocumentIntelligenceFlows';
import { DocumentViewer } from './DocumentViewer';
import { StepDocumentLayout } from './StepDocumentLayout';
import { StepDataModel } from './StepDataModel';
import { StepDataQuality } from './StepDataQuality';
import { StepFooter } from './StepFooter';
import { StepHeader } from './StepHeader';
import { ExtractionData } from './ExtractionData';
import { useExtractDocumentMutation } from '../../../queries/documentIntelligence';
import {
  buildExtractionSchemaFromLayout,
  convertParseResultToFields,
  convertParseResultToTables,
} from '../utils/dataTransformations';

interface DocumentIntelligenceViewProps {
  documentData: DocumentData;
  onClose: () => void;
}

export const DocumentIntelligenceView: FC<DocumentIntelligenceViewProps> = ({ documentData, onClose }) => {
  const { flowType } = documentData;
  const isProcessing = useDocumentIntelligenceStore((state) => state.isProcessing);
  const processingStep = useDocumentIntelligenceStore((state) => state.processingStep);
  const currentFlowType = useDocumentIntelligenceStore((state) => state.currentFlowType);
  const isDataModelNameDialogOpen = useDocumentIntelligenceStore((state) => state.isDataModelNameDialogOpen);
  const openDialog = useDocumentIntelligenceStore((state) => state.openDataModelNameDialog);
  const closeDialog = useDocumentIntelligenceStore((state) => state.closeDataModelNameDialog);
  const processingError = useDocumentIntelligenceStore((state) => state.processingError);
  const schemaModified = useDocumentIntelligenceStore((state) => state.schemaModified);
  const layoutFields = useDocumentIntelligenceStore((state) => state.layoutFields);
  const layoutTables = useDocumentIntelligenceStore((state) => state.layoutTables);
  const documentLayout = useDocumentIntelligenceStore((state) => state.documentLayout);
  const setProcessingState = useDocumentIntelligenceStore((state) => state.setProcessingState);
  const setExtractedData = useDocumentIntelligenceStore((state) => state.setExtractedData);
  const setOriginalGeneratedSchema = useDocumentIntelligenceStore((state) => state.setOriginalGeneratedSchema);
  const setStoreLayoutFields = useDocumentIntelligenceStore((state) => state.setLayoutFields);
  const setStoreLayoutTables = useDocumentIntelligenceStore((state) => state.setLayoutTables);
  const setSchemaModified = useDocumentIntelligenceStore((state) => state.setSchemaModified);

  const { handleDataModelNameSave } = useDataModelNameDialogSave();
  const { addSnackbar } = useSnackbar();
  const extractDocumentMutation = useExtractDocumentMutation({});
  const { currentStep, availableSteps, isLastStep, goToNextStep, goToPreviousStep } = useStepNavigation(flowType);
  const { stepperWidth, handleMouseDown, minStepperWidth } = useResizablePanel();
  const { handleComplete, handleRetryDocumentLayoutFlow, handleRetryDataModelFlow } = useFlowHandlers();

  // Track re-extraction loading state
  const [isReExtracting, setIsReExtracting] = useState(false);

  // Handle Re-Run Extract with modified schema
  const handleReRunExtract = useCallback(async () => {
    try {
      setProcessingState(true, 'Re-extracting with updated schema...');

      // Build the current schema from layoutFields and layoutTables
      const currentSchema = buildExtractionSchemaFromLayout(layoutFields, layoutTables);

      // Re-extract with the modified schema
      const extractedData = await extractDocumentMutation.mutateAsync({
        threadId: documentData.threadId,
        fileName: documentData.fileRef?.name || '',
        documentLayout: {
          extraction_schema: currentSchema,
          prompt: documentLayout?.prompt ?? undefined,
        },
      });

      // Update the extracted data in store
      setExtractedData(extractedData);

      // Update the original generated schema with the new modified schema
      setOriginalGeneratedSchema(currentSchema);

      // Convert extracted data back to fields/tables
      const extractedFields = convertParseResultToFields(extractedData, currentSchema);
      const extractedTables = convertParseResultToTables(extractedData, currentSchema);

      // Merge extracted data with existing fields, preserving user modifications like layout_description
      const updatedFields = layoutFields.map((existingField) => {
        const extractedField = extractedFields.find((ef) => ef.name === existingField.name);
        if (extractedField) {
          return {
            ...existingField,
            value: extractedField.value,
            description: existingField.description || extractedField.description,
            layout_description: existingField.layout_description || extractedField.layout_description,
            citationId: extractedField.citationId,
          };
        }
        return existingField;
      });

      // Add any new fields that weren't in the original layout
      const newFields = extractedFields.filter((ef) => !layoutFields.some((existing) => existing.name === ef.name));

      // Merge extracted data with existing tables, preserving user modifications
      const updatedTables = layoutTables.map((existingTable) => {
        const extractedTable = extractedTables.find((et) => et.name === existingTable.name);
        if (extractedTable) {
          // Merge column metadata, preserving layout_description from existing columns
          const mergedColumnsMeta = { ...extractedTable.columnsMeta };
          Object.keys(mergedColumnsMeta).forEach((columnName) => {
            if (existingTable.columnsMeta[columnName]) {
              mergedColumnsMeta[columnName] = {
                ...mergedColumnsMeta[columnName],
                layout_description:
                  existingTable.columnsMeta[columnName].layout_description ||
                  mergedColumnsMeta[columnName].layout_description,
              };
            }
          });

          return {
            ...existingTable,
            data: extractedTable.data,
            columns: extractedTable.columns,
            columnsMeta: mergedColumnsMeta,
            layout_description: existingTable.layout_description || extractedTable.layout_description,
          };
        }
        return existingTable;
      });

      // Add any new tables that weren't in the original layout
      const newTables = extractedTables.filter((et) => !layoutTables.some((existing) => existing.name === et.name));

      // Update with merged data
      setStoreLayoutFields([...updatedFields, ...newFields]);
      setStoreLayoutTables([...updatedTables, ...newTables]);

      // Clear modified flag
      setSchemaModified(false);

      addSnackbar({ message: 'Document re-extracted successfully', variant: 'success' });
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Failed to re-extract document';
      addSnackbar({ message: errorMsg, variant: 'danger' });
    } finally {
      setProcessingState(false);
    }
  }, [
    layoutFields,
    layoutTables,
    documentLayout,
    documentData.threadId,
    documentData.fileRef,
    extractDocumentMutation,
    setExtractedData,
    setOriginalGeneratedSchema,
    setStoreLayoutFields,
    setStoreLayoutTables,
    setSchemaModified,
    addSnackbar,
    setProcessingState,
  ]);

  // Create step map to render the correct component based on current step
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const stepMap: Record<StepType, FC<any>> = {
    document_layout: StepDocumentLayout,
    data_model: StepDataModel,
    data_quality: StepDataQuality,
  };

  const StepComponent = stepMap[currentStep];
  const [showExtractionData, setShowExtractionData] = useState(false);

  const isParseDocumentFlow = (currentFlowType || flowType) === 'parse_current_document';

  const onComplete = async () => {
    await handleComplete({
      currentStep,
      goToNextStep,
      openDataModelNameDialog: openDialog,
      onClose,
      documentData,
      isLastStep,
    });
  };

  const onCancel = () => {
    onClose();
  };

  const onRetryDocumentLayout = () => {
    handleRetryDocumentLayoutFlow(documentData);
  };

  const onRetryDataModel = () => {
    handleRetryDataModelFlow(documentData);
  };

  return (
    <>
      {/* Error State - Only show for non-form validation errors */}
      {processingError && !processingError.includes('already exists') && (
        <Banner message="An error occurred" description={processingError} icon={IconAlert} variant="error">
          {processingError.includes('document ingestion failed') ? (
            <Button variant="ghost" size="small" iconAfter={IconRefresh} onClick={onRetryDataModel}>
              Retry Ingestion
            </Button>
          ) : (
            <Button
              variant="ghost"
              size="small"
              iconAfter={IconRefresh}
              onClick={currentStep === 'document_layout' ? onRetryDocumentLayout : onRetryDataModel}
            >
              Restart
            </Button>
          )}
        </Banner>
      )}

      {/* Main Layout - Document Viewer + Stepper */}
      <Box display="flex" gap="$16" flex="1" height="100%" width="100%" maxWidth="100%" overflow="scroll">
        {/* DOCUMENT VIEWER */}
        <Box display="flex" flexDirection="column" flex="1" height="100%" minWidth="600px">
          <DocumentViewer isReadOnly={isParseDocumentFlow} />
        </Box>

        {/* STEPPER PANEL */}
        <Box
          display="flex"
          style={{ width: `${stepperWidth}px`, position: 'relative' }}
          minWidth={`${minStepperWidth}px`}
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

          {/* Stepper Content */}
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
              {!isParseDocumentFlow && (
                <>
                  <Box p="$24" width="75%" margin="0 auto">
                    <StepHeader currentStep={currentStep} availableSteps={availableSteps} />
                  </Box>
                  <Divider />
                </>
              )}

              {/* STEPPER CONTENT */}
              <Box
                flex="1"
                overflow="auto"
                padding="$16"
                minHeight="0"
                style={{
                  scrollbarWidth: 'none',
                  msOverflowStyle: 'none',
                }}
              >
                <Snackbar>
                  {showExtractionData ? (
                    <ExtractionData />
                  ) : (
                    <StepComponent
                      documentData={documentData}
                      isReadOnly={isProcessing}
                      isProcessing={isProcessing}
                      processingStep={processingStep}
                      onReExtractLoadingChange={setIsReExtracting}
                    />
                  )}
                </Snackbar>
              </Box>

              {/* STEPPER FOOTER */}
              <Box padding="$8" backgroundColor="background.primary" flexShrink="0">
                <Box display="flex" alignItems="center" justifyContent="space-between" gap="$16">
                  <Box display="flex" alignItems="center" gap="$16">
                    <Switch
                      aria-labelledby="show-extraction-data"
                      value=""
                      checked={showExtractionData}
                      onChange={(e) => setShowExtractionData(e.target.checked)}
                      disabled={isProcessing}
                    />
                    <Typography>View as JSON</Typography>
                  </Box>
                  <StepFooter
                    flowType={currentFlowType}
                    currentStep={currentStep}
                    isDisabled={isProcessing || isReExtracting}
                    goToPreviousStep={goToPreviousStep}
                    onComplete={onComplete}
                    onCancel={onCancel}
                    schemaModified={schemaModified}
                    handleRerunExtractClick={handleReRunExtract}
                    isReRunning={extractDocumentMutation.isPending}
                  />
                </Box>
              </Box>
            </Box>
          </Box>
        </Box>
      </Box>

      {/* Data Model Name Dialog */}
      <DataModelNameDialog
        open={isDataModelNameDialogOpen}
        onClose={closeDialog}
        onSave={async (name, description) => {
          try {
            await handleDataModelNameSave({
              name,
              description,
              fileRef: documentData.fileRef,
              threadId: documentData.threadId,
              agentId: documentData.agentId,
              onSuccess: () => {
                addSnackbar({
                  message: `Data model "${name}" created and document ingested successfully!`,
                  variant: 'success',
                  close: true,
                });

                goToNextStep();
              },
            });
          } catch (error) {
            addSnackbar({
              message: `Failed to save data model: ${error}`,
              variant: 'danger',
              close: true,
            });
          }
        }}
        fileRef={documentData.fileRef}
        threadId={documentData.threadId}
        agentId={documentData.agentId}
        isProcessing={isProcessing}
        processingStep={processingStep}
        error={processingError || undefined}
      />
    </>
  );
};
