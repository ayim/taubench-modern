import { z } from 'zod';

export const CreateAgentFormSchema = z.object({
  name: z.string().min(1),
  llmId: z.string().min(1),
  mode: z.enum(['conversational', 'worker']),
});

export type CreateAgentFormSchema = z.infer<typeof CreateAgentFormSchema>;
