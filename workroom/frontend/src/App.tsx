import { ThemeProvider } from '@sema4ai/theme';
import { ViewportProvider } from '@sema4ai/components';
import { AuthProvider, VirtualRoomMeta } from '@sema4ai/robocloud-ui-utils';
import { PlatformProvider, Platform } from '@sema4ai/agent-components';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/ReactToastify.css';

import { getAuthOptions, type AuthOptions } from '~/config/auth';
import { RouterProvider } from './components/providers/Router';
import { QueryClientProvider } from './components/providers/QueryClient';
import { ProtectedRoute } from './components/ProtectedRoute';
import { useEffect, useState } from 'react';
import { ACE_WORKROOM_VERSION } from './version.ts';
import { TransitionLoader } from './components/Loaders.tsx';
import { useMeta } from './hooks/meta.ts';

export const App = () => {
  useEffect(() => {
    console.log(`ACE workroom: ${ACE_WORKROOM_VERSION}`);
  }, []);

  const [authOptions, setAuthOptions] = useState<AuthOptions | undefined>(undefined);
  const meta = useMeta();

  useEffect(() => {
    const getOptionsAsync = async () => {
      const options = await getAuthOptions();
      setAuthOptions(options);
    };

    getOptionsAsync();
  }, []);

  if (!authOptions || !meta) {
    return (
      <ThemeProvider name="light">
        <TransitionLoader />
      </ThemeProvider>
    );
  }

  if (authOptions.bypassAuth) {
    return (
      <ThemeProvider name="light">
        <PlatformProvider value={Platform.WORKROOM}>
          <ToastContainer />
          <ViewportProvider>
            <QueryClientProvider>
              <ProtectedRoute bypassAuth={authOptions.bypassAuth}>
                <RouterProvider />
              </ProtectedRoute>
            </QueryClientProvider>
          </ViewportProvider>
        </PlatformProvider>
      </ThemeProvider>
    );
  }

  return (
    <ThemeProvider name="light">
      <PlatformProvider value={Platform.WORKROOM}>
        <ToastContainer />
        <ViewportProvider>
          <AuthProvider authOptions={authOptions} meta={meta as VirtualRoomMeta}>
            <QueryClientProvider>
              <ProtectedRoute>
                <RouterProvider />
              </ProtectedRoute>
            </QueryClientProvider>
          </AuthProvider>
        </ViewportProvider>
      </PlatformProvider>
    </ThemeProvider>
  );
};
