import { NEW_CHAT_STARTING_MSG } from '../lib/constants';
import { useAgentQuery } from '../queries/agents';

/**
 * Hook to get the starting message for a new thread
 * If the agent has a conversation starter, it will be used as a user message
 * Otherwise, the default starting message will be used as an agent message
 */
export const useThreadStartingMessage = ({ agentId }: { agentId: string }) => {
  const { data: agent } = useAgentQuery({ agentId });

  if (!agent) {
    return {
      message: NEW_CHAT_STARTING_MSG,
      isUserMessage: false,
    };
  }

  const conversationStarter = agent.extra?.conversation_starter as string | undefined;
  
  if (conversationStarter) {
    return {
      message: conversationStarter,
      isUserMessage: true,
    };
  }
  
  return {
    message: NEW_CHAT_STARTING_MSG,
    isUserMessage: false,
  };
};
