import { createContext, FC } from 'react';
import { FieldError, FieldErrors } from 'react-hook-form';
import z from 'zod';

import { SemanticModel } from '~/queries/semanticData';
import { InspectedTableInfo } from '~/queries/dataConnections';
import { getTableDimensions } from '../../../../lib/SemanticDataModels';

export enum DataSourceType {
  File = 'file',
  Database = 'database',
  Import = 'import',
}

export type DatabaseInspectionState = {
  isLoading: boolean;
  error: string | undefined;
  errorDetails?: string;
  inspectionResult: InspectedTableInfo | undefined;
  requiresInspection: boolean;
};

export const DataConnectionFormContext = createContext<{
  databaseInspectionState: DatabaseInspectionState;
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  setDatabaseInspectionState: (state: DatabaseInspectionState) => void;
  forceModelRegeneration: boolean;
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  setForceModelRegeneration: (force: boolean) => void;
  onSubmit: () => void;
  validationErrors: string[];
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  setValidationErrors: (errors: string[]) => void;
}>({
  databaseInspectionState: {
    isLoading: false,
    error: undefined,
    inspectionResult: undefined,
    requiresInspection: false,
  },
  setDatabaseInspectionState: () => {},
  onSubmit: () => {},
  forceModelRegeneration: false,
  setForceModelRegeneration: () => {},
  validationErrors: [],
  setValidationErrors: () => {},
});

export const DataConnectionFormSchema = z.object({
  dataConnectionId: z.string().optional(),
  dataConnectionName: z.string().optional(),
  fileRefId: z.string().optional(),
  description: z.string().optional(),
  name: z.string().optional(),
  dataSelection: z.array(
    z.object({
      name: z.string().min(1),
      columns: z.array(
        z.object({
          name: z.string(),
          data_type: z.string().min(1),
          sample_values: z.array(z.any()).optional(),
          description: z.string().optional(),
          synonyms: z.array(z.string()).optional(),
        }),
      ),
    }),
  ),
  tables: SemanticModel.shape.tables.optional(),
  relationships: SemanticModel.shape.relationships.optional(),
  verifiedQueries: SemanticModel.shape.verified_queries.optional(),
});

export const semanticModelToFormSchema = (semanticModel: SemanticModel) => {
  return {
    name: semanticModel.name,
    dataConnectionId: semanticModel.tables[0].base_table.data_connection_id,
    dataConnectionName: semanticModel.tables[0].base_table.data_connection_name,
    fileRefId: semanticModel.tables[0].base_table.file_reference?.file_ref,
    description: semanticModel.description,
    dataSelection: semanticModel.tables.map((table) => {
      return {
        name: table.base_table.table,
        columns: getTableDimensions(table).map((dimension) => {
          return {
            name: dimension.expr,
            data_type: dimension.data_type,
            sample_values: dimension.sample_values,
            synonyms: dimension.synonyms,
            description: dimension.description,
          };
        }),
      };
    }),
    tables: semanticModel.tables,
    relationships: semanticModel.relationships,
    verifiedQueries: semanticModel.verified_queries,
  } satisfies DataConnectionFormSchema;
};

export const defaultFormDataValues: DataConnectionFormSchema = {
  dataConnectionId: undefined,
  dataConnectionName: undefined,
  fileRefId: undefined,
  description: undefined,
  name: undefined,
  dataSelection: [],
  tables: undefined,
};

/**
 * Check if a semantic model has tables that reference data frames
 * (no data_connection_id or data_connection_name and no file_reference).
 */
export const hasDataFrameReferences = (semanticModel: SemanticModel): boolean => {
  return semanticModel.tables.some(
    (table) =>
      !table.base_table.data_connection_id &&
      !table.base_table.data_connection_name &&
      !table.base_table.file_reference,
  );
};

/**
 * Check if a semantic model has tables that require a data connection.
 */
export const requiresDataConnection = (semanticModel: SemanticModel): boolean => {
  return semanticModel.tables.some(
    (table) => !!table.base_table.data_connection_id || !!table.base_table.data_connection_name,
  );
};

export type DataConnectionFormSchema = z.infer<typeof DataConnectionFormSchema>;

export enum ConfigurationStep {
  DataConnection = 0,
  DataSelection = 1,
  ModelEdition = 2,
  ImportDataConnection = 3,
  SuccessCreation = 4,
  SuccessImport = 6,
  Processing = 7,
  ImportWithErrors = 8,
}

type ConfigurationStepProps = {
  onClose: () => void;
  setActiveStep: (step: ConfigurationStep) => void;
};

export type ConfigurationStepView<T = unknown> = FC<ConfigurationStepProps & T>;

export const hasDataSelectionChanged = (payload: DataConnectionFormSchema) => {
  const dataSelectionAdded = payload.dataSelection.some((selection) => {
    const table = payload.tables?.find((curr) => curr.base_table.table === selection.name);

    if (!table) {
      return true;
    }

    const dimensions = getTableDimensions(table);

    return selection.columns.some((column) => {
      return dimensions.findIndex((dimension) => dimension.expr === column.name) < 0;
    });
  });

  const dataSelectionRemoved = !!payload.tables?.some((table) => {
    const selections = payload.dataSelection.find((curr) => curr.name === table.base_table.table);

    if (!selections) {
      return true;
    }

    const dimensions = getTableDimensions(table);

    return dimensions.some((column) => {
      return selections.columns.findIndex((selection) => column.expr === selection.name) < 0;
    });
  });

  return dataSelectionAdded || dataSelectionRemoved;
};

export const hasModelChanged = (currentPayload: DataConnectionFormSchema, semanticModel: SemanticModel): boolean => {
  const previousPayload = semanticModelToFormSchema(semanticModel);
  return JSON.stringify(previousPayload) !== JSON.stringify(currentPayload);
};

const isFieldError = (error: unknown): error is FieldError => {
  return error !== null && typeof error === 'object' && 'message' in error;
};

/**
 * Recursively extract error messages from nested error objects, retaining the context
 * of the field hierarchy.
 */
const extractNestedErrors = (errorObj: unknown, prefix: string, messages: string[]): void => {
  if (!errorObj || typeof errorObj !== 'object') return;

  if (isFieldError(errorObj)) {
    messages.push(`${prefix}: ${errorObj.message}`);
    return;
  }

  if (Array.isArray(errorObj)) {
    errorObj.forEach((item, index) => {
      if (item) {
        extractNestedErrors(item, `${prefix}[${index + 1}]`, messages);
      }
    });
    return;
  }

  Object.entries(errorObj as Record<string, unknown>).forEach(([key, value]) => {
    if (value) {
      const newPrefix = prefix ? `${prefix}.${key}` : key;
      extractNestedErrors(value, newPrefix, messages);
    }
  });
};

/**
 * Format SDM form validation errors into user-friendly messages for snackbar display.
 */
export const formatSDMValidationErrors = (
  errors: FieldErrors<DataConnectionFormSchema>,
  getFieldValue: <T>(path: string) => T,
): string[] => {
  const messages: string[] = [];

  // Simple top-level fields
  if (errors.name?.message) {
    messages.push(`Name: ${errors.name.message}`);
  }
  if (errors.description?.message) {
    messages.push(`Description: ${errors.description.message}`);
  }
  if (errors.dataConnectionId?.message) {
    messages.push(`Data Connection: ${errors.dataConnectionId.message}`);
  }
  if (errors.dataConnectionName?.message) {
    messages.push(`Data Connection Name: ${errors.dataConnectionName.message}`);
  }
  if (errors.fileRefId?.message) {
    messages.push(`File Reference: ${errors.fileRefId.message}`);
  }
  if (errors.relationships) {
    if (isFieldError(errors.relationships)) {
      messages.push(`Relationships: ${errors.relationships.message}`);
    } else if (Array.isArray(errors.relationships)) {
      errors.relationships.forEach((relError, index) => {
        if (!relError) return;
        const relName = getFieldValue<string>(`relationships.${index}.name`) || `Relationship ${index + 1}`;
        Object.entries(relError).forEach(([field, fieldError]) => {
          if (isFieldError(fieldError)) {
            messages.push(`${relName}.${field}: ${fieldError.message}`);
          }
        });
      });
    }
  }

  // Verified queries array
  const vqErrors = errors.verifiedQueries;
  if (vqErrors && Array.isArray(vqErrors)) {
    vqErrors.forEach((vqError, index) => {
      if (!vqError) return;
      const queryName = getFieldValue<string>(`verifiedQueries.${index}.name`) || `Query ${index + 1}`;

      if (vqError.name?.message) messages.push(`${queryName}: ${vqError.name.message}`);
      if (vqError.sql?.message) messages.push(`${queryName}: ${vqError.sql.message}`);
      if (vqError.nlq?.message) messages.push(`${queryName}: ${vqError.nlq.message}`);
      if (isFieldError(vqError.sql_errors)) messages.push(`${queryName}: ${vqError.sql_errors.message}`);
      if (isFieldError(vqError.nlq_errors)) messages.push(`${queryName}: ${vqError.nlq_errors.message}`);
      if (isFieldError(vqError.name_errors)) messages.push(`${queryName}: ${vqError.name_errors.message}`);
      if (isFieldError(vqError.parameter_errors)) messages.push(`${queryName}: ${vqError.parameter_errors.message}`);
    });
  }

  // Data selection array
  const dsErrors = errors.dataSelection;
  if (dsErrors && Array.isArray(dsErrors)) {
    dsErrors.forEach((dsError, index) => {
      if (!dsError) return;
      const tableName = getFieldValue<string>(`dataSelection.${index}.name`) || `Table ${index + 1}`;

      if (dsError.name?.message) {
        messages.push(`${tableName}: ${dsError.name.message}`);
      }

      const colErrors = dsError.columns;
      if (colErrors && Array.isArray(colErrors)) {
        colErrors.forEach((colError, colIndex) => {
          if (!colError) return;
          const colName =
            getFieldValue<string>(`dataSelection.${index}.columns.${colIndex}.name`) || `Column ${colIndex + 1}`;

          if (colError.name?.message) messages.push(`${tableName}.${colName}: ${colError.name.message}`);
          if (colError.data_type?.message) messages.push(`${tableName}.${colName}: ${colError.data_type.message}`);
        });
      }
    });
  }

  // Tables array - use recursive extraction for deeply nested errors
  const tablesErrors = errors.tables;
  if (tablesErrors && Array.isArray(tablesErrors)) {
    tablesErrors.forEach((tableError, index) => {
      if (!tableError) return;
      const tableName = getFieldValue<string>(`tables.${index}.name`) || `Table ${index + 1}`;
      extractNestedErrors(tableError, tableName, messages);
    });
  }

  // Fallback if no specific messages but errors exist
  if (messages.length === 0 && Object.keys(errors).length > 0) {
    messages.push(`Validation failed for: ${Object.keys(errors).join(', ')}`);
  }

  return messages;
};

export const tablesToDataSelection = (
  inspection: InspectedTableInfo,
  semanticModel?: SemanticModel,
): DataConnectionFormSchema['dataSelection'] => {
  return inspection.tables
    .filter((table) => !semanticModel || semanticModel.tables.find((curr) => curr.base_table.table === table.name))
    .map((table) => {
      return {
        name: table.name,
        columns: table.columns
          .filter((column) => {
            if (!semanticModel) {
              return true;
            }

            const modelTable = semanticModel.tables.find((curr) => curr.base_table.table === table.name);
            if (!modelTable) {
              return false;
            }
            const modelDimensions = getTableDimensions(modelTable);
            return modelDimensions.findIndex((dimension) => dimension.expr === column.name) > -1;
          })
          .map((column) => {
            return {
              name: column.name,
              data_type: column.data_type,
              sample_values: column.sample_values || undefined,
              synonyms: column.synonyms || undefined,
            };
          }),
      };
    });
};
