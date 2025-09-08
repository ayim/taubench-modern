import { Avatar, Box, Divider, Menu } from '@sema4ai/components';
import { IconLogOut, IconMoon, IconSun } from '@sema4ai/icons';
import { useAuth } from '@sema4ai/robocloud-ui-utils';

import { useAuth as useAuthContext } from '~/components/ProtectedRoute';
import { useUIState } from '~/components/providers/Theme';

export const UserMenu = () => {
  const { logout } = useAuth();
  const { bypassAuth } = useAuthContext();
  const { theme, setTheme } = useUIState();

  if (!bypassAuth) {
    return <Box />;
  }

  return (
    <Menu trigger={<Avatar placeholder="U" as="button" />}>
      <Menu.Item
        onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
        icon={theme === 'dark' ? <IconSun color="yellow50" /> : IconMoon}
      >
        {theme === 'dark' ? 'Light' : 'Dark'} mode
      </Menu.Item>
      <Divider />
      <Menu.Item onClick={() => logout()} icon={IconLogOut}>
        Logout
      </Menu.Item>
    </Menu>
  );
};
