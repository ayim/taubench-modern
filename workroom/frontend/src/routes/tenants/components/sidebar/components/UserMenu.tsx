import { Avatar, Box, Menu } from '@sema4ai/components';
import { IconHelp, IconLogOut, IconMoon, IconSun, IconUserCircle } from '@sema4ai/icons';
import { useAuth } from '@sema4ai/robocloud-ui-utils';
import { FC, useCallback, useMemo } from 'react';

import { useAuth as useAuthContext } from '~/components/ProtectedRoute';
import { useUIState } from '~/components/providers/Theme';
import { useMeta } from '~/hooks/meta';
import { resolveWorkroomURL } from '~/lib/utils';
import { EXTERNAL_LINKS } from '~/config/externalLinks';

type Props = {
  profilePictureUrl?: string;
};

export const UserMenu: FC<Props> = ({ profilePictureUrl }) => {
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
    <Menu
      trigger={
        <Box
          as="button"
          width="36px"
          height="36px"
          display="flex"
          borderRadius="30px"
          backgroundColor="transparent"
          alignItems="center"
          justifyContent="center"
        >
          {(profilePictureUrl && <Avatar alt="User" src={profilePictureUrl} size="small" />) || (
            <IconUserCircle color="content.primary" />
          )}
        </Box>
      }
    >
      <Menu.Item
        onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
        icon={theme === 'dark' ? <IconSun color="yellow50" /> : IconMoon}
      >
        {theme === 'dark' ? 'Light' : 'Dark'} mode
      </Menu.Item>
      <Menu.Link href={EXTERNAL_LINKS.MAIN_WORKROOM_HELP} target="_blank" icon={IconHelp}>
        Help
      </Menu.Link>
      {canLogout && (
        <>
          <Menu.Item onClick={handleLogout} icon={IconLogOut}>
            Log out
          </Menu.Item>
        </>
      )}
    </Menu>
  );
};
