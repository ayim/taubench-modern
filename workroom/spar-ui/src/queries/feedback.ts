import { createSparMutation } from "./shared";

export const useSendFeedbackMutation = createSparMutation<{ agentId: string, threadId: string }, { feedback: string, comment: string }>()(
  ({ sparAPIClient, agentId, threadId }) => ({
    mutationFn: async ({feedback, comment }) => {
      if (!sparAPIClient.sendFeedback) {
        throw new Error('Feedback functionality is not available');
      }
      
      const success = await sparAPIClient.sendFeedback({ agentId, threadId, feedback, comment });

      if (!success) {
        throw new Error('Failed to send feedback');
      }
      
      return success;
    },
  }),
);