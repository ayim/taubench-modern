import { FC } from 'react';
import z from 'zod';

export const DataConnectionFormSchema = z.object({
  dataConnectionId: z.string().min(1),
  description: z.string().optional(),
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
});

export type DataConnectionFormSchema = z.infer<typeof DataConnectionFormSchema>;

export enum ConfigurationStep {
  DataConnection = 0,
  DataSelection = 1,
  ModelCreation = 2,
}

type ConfigurationStepProps = {
  onClose: () => void;
  setActiveStep: (step: ConfigurationStep) => void;
};

export type ConfigurationStepView = FC<ConfigurationStepProps>;
