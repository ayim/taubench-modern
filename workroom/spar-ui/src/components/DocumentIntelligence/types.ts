import { ChangeEvent } from 'react';

// Document Intelligence Types
export type FlowType =
  | 'create_data_model_plus_new_layout'
  | 'create_doc_layout_from_existing_data_model'
  | 'parse_current_document'
  | 'show_read_only_results';

export type DocumentData = {
  flowType: FlowType;
  fileRef: File;
  threadId: string;
  agentId: string;
  dataModelName?: string;
};

// UI-specific types for Document Intelligence components
export interface LayoutFieldRow {
  id: string;
  type: string;
  required: boolean;
  name: string;
  value?: string;
  description?: string;
  layout_description?: string;
  citationId?: number;
}

export interface LayoutTableRow {
  id: string;
  required: boolean;
  description?: string;
  layout_description?: string;
  name: string;
  columns: string[];
  columnsMeta: Record<string, { type: string; required: boolean; description?: string; layout_description?: string }>;
  data: Record<string, string>[];
}

// Step type for stepper navigation
export type StepType = 'document_layout' | 'data_model' | 'data_quality';

// Row props for field management in tables
export interface FieldRowProps {
  onChange: (id: string, key: 'name' | 'value') => (e: ChangeEvent<HTMLInputElement>) => void;
  onSaveSpecialHandling: (fieldId: string, instructions: string) => void;
  onDelete?: (id: string) => void;
  showAnnotateButtons?: boolean;
  showDeleteButton?: boolean;
  readOnlyFields?: boolean;
  onBlur?: (id: string, key: 'name' | 'value') => (e: React.FocusEvent<HTMLInputElement>) => void;
  onKeyDown?: (id: string, key: 'name' | 'value') => (e: React.KeyboardEvent<HTMLInputElement>) => void;
  label?: string;
}

// Utility function to convert LayoutTableRow to table columns
export const getTableColumns = (table: LayoutTableRow) => {
  return table.columns.map((column) => ({
    id: column,
    title: column.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase()),
    sortable: true,
    width: 120,
  }));
};
