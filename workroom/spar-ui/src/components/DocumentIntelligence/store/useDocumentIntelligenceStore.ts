import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import type { components } from '@sema4ai/agent-server-interface';
import { ServerResponse } from '../../../queries/shared';
import { LayoutFieldRow, LayoutTableRow, FlowType } from '../types';
import { removeCitationFromExtractedData } from '../utils/dataTransformations';


type ParseDocumentResponsePayload = ServerResponse<'post', '/api/v2/document-intelligence/documents/parse'>;
type ExtractDocumentResponsePayload = ServerResponse<'post', '/api/v2/document-intelligence/documents/extract'>;
type IngestDocumentResponsePayload = ServerResponse<'post', '/api/v2/document-intelligence/documents/ingest'>;
type ValidationRule = components['schemas']['ValidationRule'];
type DataModel = components['schemas']['DataModel'];
type DataModelPayload = components['schemas']['DataModelPayload'];
type DocumentLayoutPayload = components['schemas']['DocumentLayoutPayload'];
type ExtractionSchemaPayload = components['schemas']['_ExtractionSchema'];

export type {
  ParseDocumentResponsePayload,
  ExtractDocumentResponsePayload,
  IngestDocumentResponsePayload,
  ValidationRule,
  DataModel,
  DataModelPayload,
  DocumentLayoutPayload,
  ExtractionSchemaPayload,
};


type QualityCheck = Partial<ValidationRule> & {
  id: string;
  name: string;
  type: string;
};

type QualityCheckResult = {
  passed: boolean;
  message?: string;
  details?: Record<string, unknown>;
};


interface DocIntelDialogState {
  isOpen: boolean;
  setIsOpen: (isOpen: boolean) => void;
  modalData: {
    flowType: FlowType;
    fileRef: File;
    threadId: string;
    agentId: string;
    dataModelName?: string;
  } | null;
  setModalData: (modalData: DocIntelDialogState['modalData']) => void;
}

interface DocumentIntelligenceState {
  fileRef: File | null;
  selectedFieldId: string | null;
  parseData: ParseDocumentResponsePayload | null;
  extractedData: ExtractDocumentResponsePayload | null;

  // Document layout state (for special handling instructions)
  documentLayout: { prompt?: string | null } | null;

  // Original generated schema from generate-schema endpoint
  originalGeneratedSchema: ExtractionSchemaPayload | null;


  layoutFields: LayoutFieldRow[];
  layoutTables: LayoutTableRow[];
  selectedFields: number[];
  selectedTableColumns: Record<string, number[]>;
  fieldToConsolidatedMap: Record<string, string>; // Maps individual field IDs to their consolidated box IDs

  isProcessing: boolean;
  processingStep: string;
  processingError: string | null;
  currentFlowType: FlowType | null;


  isDataModelNameDialogOpen: boolean;
  dataModelNameDialogData: {
    name: string;
    description: string;
  } | null;
  isGeneratingDescription: boolean;

  dataQualityChecks: QualityCheck[];
  dataQualityChecksError: string | null;
  qualityCheckResults: Record<string, QualityCheckResult>;
  dataQualityPrompt: string | null;
  ingestedDocument: IngestDocumentResponsePayload | null;
  dataModel: DataModelPayload | null;
  activeRequests: Map<string, AbortController>;
  isCancelled: boolean;
  flowExecuted: boolean;

  // Actions
  setFileRef: (fileRef: File | null) => void;
  setSelectedFieldId: (fieldId: string | null) => void;

  setParseData: (data: ParseDocumentResponsePayload | null) => void;
  setExtractedData: (data: ExtractDocumentResponsePayload | null) => void;
  setDocumentLayout: (layout: DocumentIntelligenceState['documentLayout']) => void;
  setOriginalGeneratedSchema: (schema: ExtractionSchemaPayload | null) => void;

  setLayoutFields: (fields: LayoutFieldRow[]) => void;
  setLayoutTables: (tables: LayoutTableRow[]) => void;
  setSelectedFields: (selectedFields: number[]) => void;
  setSelectedTableColumns: (selectedTableColumns: Record<string, number[]>) => void;
  setFieldToConsolidatedMap: (mapping: Record<string, string>) => void;

  setProcessingState: (isProcessing: boolean, step?: string, error?: string | null) => void;
  setProcessingError: (error?: string | null) => void;
  clearProcessingState: () => void;

  setCurrentFlowType: (flowType: FlowType | null) => void;

  openDataModelNameDialog: () => void;
  closeDataModelNameDialog: () => void;
  setDataModelNameDialogData: (data: { name: string; description: string } | null) => void;
  setIsGeneratingDescription: (generating: boolean) => void;


  setDataQualityChecks: (checks: QualityCheck[]) => void;
  setDataQualityChecksError: (error: string | null) => void;
  setQualityCheckResult: (
    ruleName: string,
    result: QualityCheckResult | null,
  ) => void;
  setDataQualityPrompt: (prompt: string | null) => void;

  setIngestedDocument: (ingestedDocument: IngestDocumentResponsePayload | null) => void;
  setDataModel: (dataModel: DataModelPayload | null) => void;


  cancelAllRequests: () => void;
  cancelRequest: (requestId: string) => void;
  isRequestActive: (requestId: string) => boolean;

  updateField: (id: string, updates: Partial<LayoutFieldRow>) => void;
  addField: (field: Omit<LayoutFieldRow, 'id'>) => LayoutFieldRow;
  removeField: (id: string) => void;
  updateTableField: (name: string, updates: Partial<LayoutTableRow>) => void;

  setFlowExecuted: (executed: boolean) => void;

  // Reset all state
  reset: () => void;
}

// Dialog store
export const useDocIntelDialogStore = create<DocIntelDialogState>()(
  devtools((set) => ({
    isOpen: false,
    setIsOpen: (isOpen: boolean) => set({ isOpen }),
    modalData: null,
    setModalData: (modalData: DocIntelDialogState['modalData']) => set({ modalData }),
  })),
);

// Main store
export const useDocumentIntelligenceStore = create<DocumentIntelligenceState>()(
  devtools((set, get) => ({
    // Initial state
    fileRef: null,
    selectedFieldId: null,
    parseData: null,
    extractedData: null,
    documentLayout: null,
    originalGeneratedSchema: null,
    layoutFields: [],
    layoutTables: [],
    selectedFields: [],
    selectedTableColumns: {},
    fieldToConsolidatedMap: {},
    isProcessing: false,
    processingStep: '',
    processingError: null,
    currentFlowType: null,
    isDataModelNameDialogOpen: false,
    dataModelNameDialogData: null,
    isGeneratingDescription: false,
    dataQualityChecks: [],
    dataQualityChecksError: null,
    qualityCheckResults: {},
    dataQualityPrompt: null,
    ingestedDocument: null,
    dataModel: null,
    activeRequests: new Map<string, AbortController>(),
    isCancelled: false,
    flowExecuted: false,

    // Actions
    setFileRef: (fileRef: File | null) => {
      set({ fileRef });
    },

    setSelectedFieldId: (fieldId: string | null) => {
      set({ selectedFieldId: fieldId });
    },

    setParseData: (data: ParseDocumentResponsePayload | null) => {
      set({ parseData: data });
    },

    setExtractedData: (data: ExtractDocumentResponsePayload | null) => {
      set({ extractedData: data });
    },

    setDocumentLayout: (layout: DocumentIntelligenceState['documentLayout']) => {
      set({ documentLayout: layout });
    },

    setOriginalGeneratedSchema: (schema: ExtractionSchemaPayload | null) => {
      set({ originalGeneratedSchema: schema });
    },

    setLayoutFields: (fields: LayoutFieldRow[]) => {
      set({ layoutFields: fields });
    },

    setLayoutTables: (tables: LayoutTableRow[]) => {
      set({ layoutTables: tables });
    },

    setSelectedFields: (selectedFields: number[]) => {
      set({ selectedFields });
    },

    setSelectedTableColumns: (selectedTableColumns: Record<string, number[]>) => {
      set({ selectedTableColumns });
    },

    setFieldToConsolidatedMap: (mapping: Record<string, string>) => {
      set({ fieldToConsolidatedMap: mapping });
    },

    setProcessingState: (isProcessing: boolean, step = '', error = null) => {
      set({ isProcessing, processingStep: step, processingError: error });
    },

    setProcessingError: (error?: string | null) => {
      set({ processingError: error });
    },

    clearProcessingState: () => {
      set({ isProcessing: false, processingStep: '', processingError: null });
    },

    setCurrentFlowType: (flowType: FlowType | null) => {
      set({ currentFlowType: flowType });
    },

    // Data Model Name Dialog actions
    openDataModelNameDialog: () => set({ isDataModelNameDialogOpen: true }),
    closeDataModelNameDialog: () => set({ isDataModelNameDialogOpen: false, dataModelNameDialogData: null }),
    setDataModelNameDialogData: (data) => set({ dataModelNameDialogData: data }),
    setIsGeneratingDescription: (generating: boolean) => set({ isGeneratingDescription: generating }),

    // Data Quality actions
    setDataQualityChecks: (checks: QualityCheck[]) => {
      set({ dataQualityChecks: checks });
    },

    setDataQualityChecksError: (error: string | null) => {
      set({ dataQualityChecksError: error });
    },

    setQualityCheckResult: (ruleName: string, result: QualityCheckResult | null) => {
      const { qualityCheckResults } = get();
      set({
        qualityCheckResults: {
          ...qualityCheckResults,
          [ruleName]: result ?? qualityCheckResults[ruleName],
        },
      });
    },

    setDataQualityPrompt: (prompt: string | null) => {
      set({ dataQualityPrompt: prompt });
    },

    // Document ingestion actions
    setIngestedDocument: (ingestedDocument: IngestDocumentResponsePayload | null) => {
      set({ ingestedDocument });
    },

    setDataModel: (dataModel: DataModelPayload | null) => {
      set({ dataModel });
    },

    // Request cancellation actions
    cancelAllRequests: () => {
      const { activeRequests } = get();
      activeRequests.forEach((controller) => {
        controller.abort();
      });
      set({
        activeRequests: new Map(),
        isCancelled: true,
        isProcessing: false,
        processingError: null,
        processingStep: 'Cancelled by user',
        extractedData: null, // Clear extracted data when cancelling
        parseData: null, // Clear parse data when cancelling
      });
    },

    cancelRequest: (requestId: string) => {
      const { activeRequests } = get();
      const controller = activeRequests.get(requestId);
      if (controller) {
        controller.abort();
        const newActiveRequests = new Map(activeRequests);
        newActiveRequests.delete(requestId);
        set({ activeRequests: newActiveRequests });
      }
    },

    isRequestActive: (requestId: string) => {
      const { activeRequests } = get();
      return activeRequests.has(requestId);
    },

    // Field management actions
    updateField: (id: string, updates: Partial<LayoutFieldRow>) =>
      set((state) => {
        const newFields = state.layoutFields.map((field) => (field.id === id ? { ...field, ...updates } : field));
        return { layoutFields: newFields };
      }),

    addField: (fieldData: Omit<LayoutFieldRow, 'id'>) => {
      const newField = {
        ...fieldData,
        id: `field-${Date.now()}`,
      };
      set((state) => ({
        layoutFields: [...state.layoutFields, newField],
      }));
      return newField;
    },

    removeField: (id: string) =>
      set((state) => {
        // Find the field being removed to get its name
        const fieldToRemove = state.layoutFields.find((field) => field.id === id);

        // Remove the field from layoutFields
        const updatedFields = state.layoutFields.filter((field) => field.id !== id);

        // If we have extractedData and the field has a name, remove the corresponding citation
        let updatedExtractedData = state.extractedData;
        if (fieldToRemove?.name && state.extractedData) {
          updatedExtractedData = removeCitationFromExtractedData(state.extractedData, fieldToRemove.name);
        }

        return {
          layoutFields: updatedFields,
          extractedData: updatedExtractedData,
        };
      }),

    // Table field management actions
    updateTableField: (name: string, updates: Partial<LayoutTableRow>) =>
      set((state) => ({
        layoutTables: state.layoutTables.map((table) => (table.name === name ? { ...table, ...updates } : table)),
      })),

    // Flow execution tracking
    setFlowExecuted: (executed: boolean) => {
      set({ flowExecuted: executed });
    },

    // Reset all state
    reset: () => {
      // Cancel any ongoing requests first
      const { activeRequests } = get();
      activeRequests.forEach((controller) => {
        controller.abort();
      });

      set({
        fileRef: null,
        selectedFieldId: null,
        parseData: null,
        extractedData: null,
        documentLayout: null,
        layoutFields: [],
        layoutTables: [],
        selectedFields: [],
        selectedTableColumns: {},
        fieldToConsolidatedMap: {},
        isProcessing: false,
        processingStep: '',
        processingError: null,
        currentFlowType: null,
        isDataModelNameDialogOpen: false,
        dataModelNameDialogData: null,
        isGeneratingDescription: false,
        dataQualityChecks: [],
        dataQualityChecksError: null,
        qualityCheckResults: {},
        dataQualityPrompt: null,
        ingestedDocument: null,
        dataModel: null,
        activeRequests: new Map<string, AbortController>(),
        isCancelled: false,
        flowExecuted: false,
      });
    },
  }),
  {
    name: 'document-intelligence-store',
  },
));
