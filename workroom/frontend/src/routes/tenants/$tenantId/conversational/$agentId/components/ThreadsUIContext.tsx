import { createContext, useContext } from 'react';

type ThreadsUIContext = {
  threadsExpanded: boolean;
  setThreadsExpanded: (threadsExpanded: boolean) => void;
  threadsHovered: boolean;
  setThreadsHovered: (threadsHovered: boolean) => void;
};

export const ThreadsUIContext = createContext<ThreadsUIContext>({
  threadsExpanded: false,
  setThreadsExpanded: () => null,
  threadsHovered: false,
  setThreadsHovered: () => null,
});

export const useThreadsUI = () => {
  return useContext(ThreadsUIContext);
};
