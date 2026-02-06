import z from 'zod';

import { Schema } from '~/queries/semanticData';

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
  // Using z.any() to avoid Zod 4 _zod property errors with shape references
  tables: z.any().optional(),
  relationships: z.any().optional(),
  verifiedQueries: z.any().optional(),
  schemas: z.array(Schema),
});

export type DataConnectionFormSchema = z.infer<typeof DataConnectionFormSchema>;
