import { createContext, useContext } from 'react';

type VioletChatContext = {
  threadId: string;
  agentId: string;
  setThreadId: (threadId: string) => void;
};

export const VioletChatContext = createContext<VioletChatContext>({
  threadId: '',
  agentId: '',
  setThreadId: () => null,
});

export const useVioletChatContext = () => useContext(VioletChatContext);
