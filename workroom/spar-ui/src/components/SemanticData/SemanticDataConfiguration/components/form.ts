import { createContext, FC } from 'react';
import z from 'zod';
import { components } from '@sema4ai/agent-server-interface';

import { SemanticModel } from '../../../../queries/semanticData';

export type InspectedTableInfo = components['schemas']['agent_platform__core__payloads__data_connection__TableInfo'];

export enum DataSourceType {
  File = 'file',
  Database = 'database',
  Import = 'import',
}

export type DatabaseInspectionState = {
  isLoading: boolean;
  error: string | undefined;
  dataTables: InspectedTableInfo[];
};

export const DataConnectionFormContext = createContext<{
  databaseInspectionState: DatabaseInspectionState;
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  setDatabaseInspectionState: (state: DatabaseInspectionState) => void;
  importErrors: string[];
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  setImportErrors: (errors: string[]) => void;
  onSubmit: () => void;
}>({
  databaseInspectionState: {
    isLoading: false,
    error: undefined,
    dataTables: [],
  },
  setDatabaseInspectionState: () => {},
  importErrors: [],
  setImportErrors: () => {},
  onSubmit: () => {},
});

export const DataConnectionFormSchema = z.object({
  dataConnectionId: z.string().optional(),
  fileRefId: z.string().optional(),
  description: z.string().optional(),
  name: z.string().optional(),
  dataSelection: z.array(
    z.object({
      name: z.string().min(1),
      columns: z.array(
        z.object({
          name: z.string().min(1),
          data_type: z.string().min(1),
          sample_values: z.array(z.any()).optional(),
          description: z.string().optional(),
          synonyms: z.array(z.string()).optional(),
        }),
      ),
    }),
  ),
  tables: SemanticModel.shape.tables.optional(),
});

export const getTableDimensions = (table: SemanticModel['tables'][number]) => {
  return (table.dimensions || [])
    .concat(table.time_dimensions || [])
    .concat(table.facts || [])
    .concat(table.metrics || []);
};

export const semanticModelToFormSchema = (semanticModel: SemanticModel) => {
  return {
    name: semanticModel.name,
    dataConnectionId: semanticModel.tables[0].base_table.data_connection_id,
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
            description: dimension.description,
            synonyms: dimension.synonyms,
          };
        }),
      };
    }),
    tables: semanticModel.tables,
  } satisfies DataConnectionFormSchema;
};

export type DataConnectionFormSchema = z.infer<typeof DataConnectionFormSchema>;

export enum ConfigurationStep {
  DataConnection = 0,
  ImportDataConnection = 3,
  DataSelection = 1,
  ModelEdition = 2,
}

type ConfigurationStepProps = {
  onClose: () => void;
  setActiveStep: (step: ConfigurationStep) => void;
};

export type ConfigurationStepView<T = unknown> = FC<ConfigurationStepProps & T>;
