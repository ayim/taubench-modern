import { NEW_CHAT_STARTING_MSG } from '../lib/constants';
import { useAgentQuery } from '../queries/agents';

/**
 * Hook to get the starting message for a new thread
 * If the agent has a conversation starter, it will be used
 * Otherwise, the default starting message will be used
 */
export const useThreadStartingMessage = ({ agentId }: { agentId: string }) => {
  const { data: agent } = useAgentQuery({ agentId });

  if (!agent) {
    return NEW_CHAT_STARTING_MSG;
  }

  const startingMessage = agent.extra?.conversation_starter as string | undefined;
  return startingMessage ?? NEW_CHAT_STARTING_MSG;
};
