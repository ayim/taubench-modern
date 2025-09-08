import { create } from 'zustand';

/**
 * Store for thread search state
 */
type ThreadSearchStore = {
  query: string;
  currentMessageIndex: number | null;
  setQuery: (query: string) => void;
  setCurrentMessageIndex: (setCurrentMessageIndex: number | null) => void;
};

export const useThreadSearchStore = create<ThreadSearchStore>((set) => ({
  query: '',
  currentMessageIndex: null,
  setQuery: (query: string) => set({ query }),
  setCurrentMessageIndex: (currentMessageIndex: number | null) => set({ currentMessageIndex }),
}));
