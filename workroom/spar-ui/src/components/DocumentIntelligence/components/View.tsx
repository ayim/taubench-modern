import { FC, useState } from 'react';
import { IconAlert, IconRefresh } from '@sema4ai/icons';
import { Box, Switch, Snackbar, Divider, Typography, Banner, Button, useSnackbar } from '@sema4ai/components';
import { StepType, DocumentData } from '../types';
import { DataModelNameDialog } from './common/DataModelNameDialog';
import { useDocumentIntelligenceStore } from '../store/useDocumentIntelligenceStore';
import { useDataModelNameDialogSave, useStepNavigation, useResizablePanel, useFlowHandlers } from '../hooks/useDocumentIntelligenceFlows';
import { DocumentViewer } from './DocumentViewer';
import { StepDocumentLayout } from './StepDocumentLayout';
import { StepDataModel } from './StepDataModel';
import { StepDataQuality } from './StepDataQuality';
import { StepFooter } from './StepFooter';
import { StepHeader } from './StepHeader';
import { ExtractionData } from './ExtractionData';

interface DocumentIntelligenceViewProps {
  documentData: DocumentData;
  onClose: () => void;
}

export const DocumentIntelligenceView: FC<DocumentIntelligenceViewProps> = ({
  documentData,
  onClose,
}) => {
  const { flowType } = documentData;
  const {
    isProcessing,
    processingStep,
    currentFlowType,
    isDataModelNameDialogOpen,
    openDataModelNameDialog: openDialog,
    closeDataModelNameDialog: closeDialog,
    processingError
  } = useDocumentIntelligenceStore();

  const { handleDataModelNameSave } = useDataModelNameDialogSave();
  const { addSnackbar } = useSnackbar();
  const {
    currentStep,
    availableSteps,
    isLastStep,
    goToNextStep,
    goToPreviousStep
  } = useStepNavigation(flowType);
  const { stepperWidth, handleMouseDown, minStepperWidth } = useResizablePanel();
  const {
    handleComplete,
    handleRetryDocumentLayoutFlow,
    handleRetryDataModelFlow
  } = useFlowHandlers();

  // Create step map to render the correct component based on current step
  const stepMap: Record<StepType, FC<{ documentData: DocumentData; isReadOnly?: boolean; isProcessing?: boolean; processingStep?: string }>> = {
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
              onClick={
                currentStep === 'document_layout'
                  ? onRetryDocumentLayout
                  : onRetryDataModel
              }
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
              backgroundColor="background.primary"
              display="flex"
              flexDirection="column"
              flex="1"
              minHeight="0"
            >
              {!isParseDocumentFlow && (
                <>
                  <Box p="$24" width="75%" margin="0 auto">
                    <StepHeader
                      currentStep={currentStep}
                      availableSteps={availableSteps}
                    />
                    </Box>
                  <Divider/>
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
                    />
                  )}
                </Snackbar>
              </Box>

              {/* STEPPER FOOTER */}
              <Box padding="$8" backgroundColor="background.subtle" flexShrink="0">
                <Box display="flex" alignItems="center" justifyContent="space-between" gap="$16">
                  <Box display="flex" alignItems="center" gap="$16">
                    <Switch
                      aria-labelledby="show-extraction-data"
                      value=""
                      checked={showExtractionData}
                      onChange={(e) => setShowExtractionData(e.target.checked)}
                      disabled={isProcessing}
                    />
                    <Typography>View Extraction</Typography>
                  </Box>
                    <StepFooter
                      flowType={currentFlowType}
                      currentStep={currentStep}
                      isDisabled={isProcessing}
                      goToPreviousStep={goToPreviousStep}
                      onComplete={onComplete}
                      onCancel={onCancel}
                      documentData={documentData}
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
