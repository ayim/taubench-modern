import z from 'zod';
import { SemanticModel } from '~/queries/semanticData';

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

export type DataConnectionFormSchema = z.infer<typeof DataConnectionFormSchema>;
