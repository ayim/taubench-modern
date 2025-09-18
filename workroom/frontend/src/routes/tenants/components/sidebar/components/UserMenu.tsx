import { Avatar, Divider, Menu } from '@sema4ai/components';
import { IconLogOut, IconMoon, IconSun } from '@sema4ai/icons';
import { useAuth } from '@sema4ai/robocloud-ui-utils';
import { useCallback, useMemo } from 'react';

import { useAuth as useAuthContext } from '~/components/ProtectedRoute';
import { useUIState } from '~/components/providers/Theme';
import { useMeta } from '~/hooks/meta';
import { resolveWorkroomURL } from '~/lib/utils';

export const UserMenu = () => {
  const { logout } = useAuth();
  const { bypassAuth } = useAuthContext();
  const { theme, setTheme } = useUIState();
  const meta = useMeta();

  const canLogout = useMemo(
    () => !bypassAuth || (meta?.deploymentType === 'spar' && meta.auth === 'session'),
    [bypassAuth, meta],
  );

  const handleLogout = useCallback(() => {
    if (meta?.deploymentType === 'spar' && meta.auth === 'session') {
      window.location.href = resolveWorkroomURL('/auth/logout');
      return;
    }

    if (!bypassAuth) {
      logout();
      return;
    }
  }, [bypassAuth, logout, meta]);

  return (
    <Menu trigger={<Avatar placeholder="U" as="button" />}>
      <Menu.Item
        onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
        icon={theme === 'dark' ? <IconSun color="yellow50" /> : IconMoon}
      >
        {theme === 'dark' ? 'Light' : 'Dark'} mode
      </Menu.Item>
      {canLogout && (
        <>
          <Divider />
          <Menu.Item onClick={handleLogout} icon={IconLogOut}>
            Log out
          </Menu.Item>
        </>
      )}
    </Menu>
  );
};
