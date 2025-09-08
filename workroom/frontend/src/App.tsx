import { useMemo } from 'react';
import { ThemeProvider } from '@sema4ai/theme';
import { Snackbar, useLocalStorage, ViewportProvider } from '@sema4ai/components';
import { ConfirmationDialogProvider } from '@sema4ai/layouts';

import { RouterProvider } from './components/providers/Router';
import { QueryClientProvider } from './components/providers/QueryClient';
import { AuthProvider } from './components/providers/AuthProvider';
import { UIStateContext } from './components/providers/Theme';
import { ProtectedRoute } from './components/ProtectedRoute';
import { ACE_WORKROOM_VERSION } from './version';

export const App = () => {
  const { storageValue: currentTheme, setStorageValue: setTheme } = useLocalStorage<'dark' | 'light'>({
    key: 'theme',
    defaultValue: 'light',
    sync: true,
  });

  const { storageValue: sidebarExpanded, setStorageValue: setSidebarExpanded } = useLocalStorage<boolean>({
    key: 'sidebar-expanded',
    defaultValue: true,
    sync: true,
  });

  const uiStateContextValue = useMemo(
    () => ({ theme: currentTheme, setTheme, sidebarExpanded, setSidebarExpanded }),
    [currentTheme, setTheme, sidebarExpanded, setSidebarExpanded],
  );

  console.log(`ACE workroom ${ACE_WORKROOM_VERSION}`);

  return (
    <ThemeProvider name={currentTheme}>
      <UIStateContext.Provider value={uiStateContextValue}>
        <Snackbar max={5}>
          <QueryClientProvider>
            <ViewportProvider>
              <ConfirmationDialogProvider>
                <AuthProvider>
                  <ProtectedRoute>
                    <RouterProvider />
                  </ProtectedRoute>
                </AuthProvider>
              </ConfirmationDialogProvider>
            </ViewportProvider>
          </QueryClientProvider>
        </Snackbar>
      </UIStateContext.Provider>
    </ThemeProvider>
  );
};
