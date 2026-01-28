import { FC, ReactNode, useEffect, useState } from 'react';
import { AuthProvider as AuthProviderBase, VirtualRoomMeta } from '@sema4ai/robocloud-ui-utils';

import { getAuthOptions, type AuthOptions } from '~/config/auth';
import { useMeta } from '~/hooks/meta';
import { FullScreenLoader } from '../Loaders';

type Props = {
  children: ReactNode;
};

export const AuthProvider: FC<Props> = ({ children }) => {
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
    return <FullScreenLoader />;
  }

  if (authOptions.bypassAuth) {
    return children;
  }

  return (
    <AuthProviderBase authOptions={authOptions} meta={meta as VirtualRoomMeta}>
      {children}
    </AuthProviderBase>
  );
};
