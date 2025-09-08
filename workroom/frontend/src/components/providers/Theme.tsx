import { createContext, useContext } from 'react';
import { Theme } from '@sema4ai/theme';

type UIStateContext = {
  theme: Theme['name'];
  setTheme: (theme: Theme['name']) => void;
  sidebarExpanded: boolean;
  setSidebarExpanded: (sidebarExpanded: boolean) => void;
};

export const UIStateContext = createContext<UIStateContext>({
  theme: 'light',
  setTheme: () => null,
  sidebarExpanded: true,
  setSidebarExpanded: () => null,
});

export const useUIState = () => {
  return useContext(UIStateContext);
};
