import { useState, useCallback } from 'react';
import { ParseOnlyDialog } from '../../ParseOnly';
import { DocumentData, DocumentIntelligenceDialog } from '../../../DocumentIntelligence';

type DocIntelDialogState = {
  interfaceType: string;
  file: File;
  agentId: string;
  threadId: string;
} | null;

/**
 * Hook to manage Document Intelligence dialog state and rendering
 * Switches between different dialog components based on interface type
 *
 * @param threadId - The thread ID for the dialogs
 * @returns Dialog state management and render function
 */
export const useDocIntelDialogManager = (threadId: string) => {
  const [dialogState, setDialogState] = useState<DocIntelDialogState>(null);

  const openDialog = useCallback(
    (params: { interfaceType: string; file: File; agentId: string }) => {
      setDialogState({
        interfaceType: params.interfaceType,
        file: params.file,
        agentId: params.agentId,
        threadId,
      });
    },
    [threadId],
  );

  const closeDialog = useCallback(() => {
    setDialogState(null);
  }, []);

  // Map interface type to legacy flow type for old DocumentIntelligenceDialog
  const getLegacyDocumentData = useCallback((): DocumentData | null => {
    if (!dialogState || dialogState.interfaceType === 'di-parse-only') {
      return null; // Parse-only uses new dialog
    }

    // Map other interface types to legacy flow types
    if (dialogState.interfaceType === 'parse-only-v1') {
      return {
        flowType: 'parse_current_document',
        fileRef: dialogState.file,
        threadId: dialogState.threadId,
        agentId: dialogState.agentId,
        dataModelName: undefined,
      };
    }

    return {
      flowType: 'parse_current_document',
      fileRef: dialogState.file,
      threadId: dialogState.threadId,
      agentId: dialogState.agentId,
      dataModelName: undefined,
    };
  }, [dialogState]);

  // Render the appropriate dialog based on interface type
  const DocIntelDialog = useCallback(() => {
    if (!dialogState) return null;

    // Route to new ParseOnlyDialog
    if (dialogState.interfaceType === 'di-parse-only') {
      return (
        <ParseOnlyDialog
          isOpen
          onClose={closeDialog}
          file={dialogState.file}
          agentId={dialogState.agentId}
          threadId={dialogState.threadId}
        />
      );
    }

    // Route to legacy DocumentIntelligenceDialog for other types - TEMPORARY so we can still access the legacy flow.
    const legacyData = getLegacyDocumentData();
    if (legacyData) {
      return <DocumentIntelligenceDialog isOpen onClose={closeDialog} documentData={legacyData} />;
    }

    return null;
  }, [dialogState, closeDialog, getLegacyDocumentData]);

  return {
    openDialog,
    closeDialog,
    DocIntelDialog,
    isOpen: dialogState !== null,
  };
};
