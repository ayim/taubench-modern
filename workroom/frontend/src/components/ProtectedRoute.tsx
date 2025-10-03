import { FC, ReactNode, createContext, useContext, useEffect, useMemo } from 'react';
import { useAuth as useAuthUtil } from '@sema4ai/robocloud-ui-utils';

import { useAuthOptions } from '~/queries/auth';
import { FullScreenLoader } from './Loaders';

type Props = {
  children?: ReactNode;
};

type AuthContext = {
  getUserToken: () => Promise<string | undefined>;
  bypassAuth: boolean;
};

const AuthContext = createContext<AuthContext>({
  getUserToken: undefined!,
  bypassAuth: false,
});

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => {
  return useContext(AuthContext);
};

export const ProtectedRoute: FC<Props> = ({ children }) => {
  const { data: authOptions, isLoading: isAuthOptionsLoading } = useAuthOptions();
  const { isLoading, isAuthenticated, redirectToLogin, getUserToken } = useAuthUtil();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      redirectToLogin(window.location.href);
    }
  }, [isLoading, isAuthenticated, getUserToken, redirectToLogin]);

  const authContext = useMemo(
    () => ({ getUserToken, bypassAuth: authOptions?.bypassAuth ?? false }),
    [getUserToken, authOptions],
  );

  if (!authOptions || (!authOptions?.bypassAuth && (isAuthOptionsLoading || isLoading || !isAuthenticated))) {
    return <FullScreenLoader />;
  }

  return <AuthContext.Provider value={authContext}>{children}</AuthContext.Provider>;
};
