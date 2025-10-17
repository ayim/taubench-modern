import { createSparMutation, QueryError, ResourceType } from './shared';

export const useSendFeedbackMutation = createSparMutation<
  { agentId: string; threadId: string },
  { feedback: string; comment: string }
>()(({ sparAPIClient, agentId, threadId }) => ({
  mutationFn: async ({ feedback, comment }) => {
    if (!sparAPIClient.sendFeedback) {
      throw new QueryError('Feedback functionality is not available', {
        code: 'not_found',
        resource: ResourceType.Feedback,
      });
    }

    const success = await sparAPIClient.sendFeedback({ agentId, threadId, feedback, comment });

    if (!success) {
      throw new QueryError('Failed to send feedback', { code: 'bad_request', resource: ResourceType.Feedback });
    }

    return success;
  },
}));
