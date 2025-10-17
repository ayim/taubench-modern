import type { components } from '@sema4ai/agent-server-interface';
import { createSparMutation } from './shared';

export type QuestionGroup = components['schemas']['QuestionGroup'];
export type Agent = components['schemas']['AgentCompat'];
export type UpsertAgentPayload = components['schemas']['UpsertAgentPayload'];

type UpdateAgentQuestionGroupsPayload = {
  question_groups: QuestionGroup[];
};

export const useUpdateAgentQuestionGroupsMutation = createSparMutation<
  Record<string, never>,
  { agentId: string; body: UpdateAgentQuestionGroupsPayload }
>()(({ /* sparAPIClient, */ queryClient }) => ({
  mutationFn: async (/* {  agentId, body } */): Promise<Agent> => {
    // TODO: Implement a PATCH endpoint to update only question_groups of an agent

    return null as unknown as Agent;
  },
  onSuccess: async (_data, { agentId }) => {
    await queryClient.invalidateQueries({ queryKey: ['agent', agentId] });
  },
}));
