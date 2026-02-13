import { z } from 'zod';

export const QuestionGroupFormData = z.object({
  title: z.string().trim(),
  questions: z.array(z.string().trim().min(1)),
});

export type QuestionGroupFormData = z.infer<typeof QuestionGroupFormData>;
