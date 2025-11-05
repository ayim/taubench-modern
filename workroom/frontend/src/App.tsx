import { useEffect, useMemo } from 'react';
import { ThemeProvider } from '@sema4ai/theme';
import { Box, Button, EmptyState, Snackbar, useLocalStorage, ViewportProvider } from '@sema4ai/components';
import { ConfirmationDialogProvider } from '@sema4ai/layouts';

import { RouterProvider } from './components/providers/Router';
import { QueryClientProvider } from './components/providers/QueryClient';
import { AuthProvider } from './components/providers/AuthProvider';
import { UIStateContext } from './components/providers/Theme';
import { ProtectedRoute } from './components/ProtectedRoute';
import { SPAR_VERSION } from './version';
import { resolveWorkroomURL } from './lib/utils';
import errorIllustration from '~/assets/error.svg';
import { TRPCProvider } from './components/TRPCProvider';

export const App = () => {
  useEffect(() => {
    console.log(`Version ${SPAR_VERSION}`);
  }, []);

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

  const loginUrl = useMemo(() => resolveWorkroomURL('/home'), []);

  const trpcUrl = useMemo(() => resolveWorkroomURL('/trpc'), []);

  // @TODO: Remove this hack - this logged-out page needs to run OUTSIDE the current auth logic,
  // as it cannot have any requests hitting the backend (besides /meta for example).
  if (/\/logged-out/.test(window.location.href)) {
    return (
      <ThemeProvider name={currentTheme}>
        <Box display="flex" justifyContent="center" flexDirection="column" maxHeight={960} height="calc(100% - 72px)">
          <EmptyState
            illustration={<img src={errorIllustration} loading="lazy" alt="" />}
            title="Logged Out"
            description="You're logged out! Please do feel free to log in again, however."
            action={
              <a href={loginUrl}>
                <Button forwardedAs="span" round>
                  Log In
                </Button>
              </a>
            }
          />
        </Box>
      </ThemeProvider>
    );
  }

  return (
    <ThemeProvider name={currentTheme}>
      <UIStateContext.Provider value={uiStateContextValue}>
        <Snackbar max={5}>
          <QueryClientProvider>
            <ViewportProvider>
              <ConfirmationDialogProvider>
                <AuthProvider>
                  <ProtectedRoute>
                    <TRPCProvider trpcUrl={trpcUrl}>
                      <RouterProvider />
                    </TRPCProvider>
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
