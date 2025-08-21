import { FC, ReactNode, createContext, useContext, useEffect, useMemo } from 'react';
import { useAuth as useAuthUtil } from '@sema4ai/robocloud-ui-utils';
import { InlineLoader } from './Loaders';

type Props = {
  bypassAuth?: boolean;
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

export const ProtectedRoute: FC<Props> = ({ bypassAuth = false, children }) => {
  const { isLoading, isAuthenticated, redirectToLogin, getUserToken } = useAuthUtil();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      console.log('Setting auth redirect:', window.location.href);
      redirectToLogin(window.location.href);
    }
  }, [isLoading, isAuthenticated, getUserToken, redirectToLogin]);

  const authContext = useMemo(() => ({ getUserToken, bypassAuth }), [getUserToken, bypassAuth]);

  if (!bypassAuth && (isLoading || !isAuthenticated)) {
    return <InlineLoader />;
  }

  return <AuthContext.Provider value={authContext}>{children}</AuthContext.Provider>;
};
