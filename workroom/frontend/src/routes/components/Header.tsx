import { cn } from '@sema4ai/agent-components';
import { Avatar, Box, Divider, Menu } from '@sema4ai/components';
import { IconChevronDown, IconLogOut } from '@sema4ai/icons';
import { IconSema4 } from '@sema4ai/icons/logos';
import { useAuth } from '@sema4ai/robocloud-ui-utils';
import { Link, useParams, useRouter } from '@tanstack/react-router';
import { FC, memo } from 'react';
import { useListUserTenantsQuery, UserTenant } from '~/queries/tenants';
import { useAuth as useAuthContext } from '~/components/ProtectedRoute';
import { useTenantContext } from '~/lib/tenantContext';
import { getTenantWorkoomRedirect } from '~/lib/utils';

const MenuItem: FC<{ tenant: UserTenant }> = memo(({ tenant }) => {
  const router = useRouter();

  return (
    <Link
      to="/$tenantId/home"
      params={{ tenantId: tenant.id }}
      tabIndex={-1}
      onClick={() => {
        const workroomRedirect = getTenantWorkoomRedirect({
          tenant,
          location: window.location,
        });

        if (workroomRedirect) {
          router.navigate({ to: workroomRedirect.href, replace: true });
          return;
        }
      }}
    >
      {({ isActive }: { isActive: boolean }) => (
        <Menu.Item
          key={tenant.id}
          aria-selected={isActive}
          className="!w-full"
          icon={<Avatar placeholder={tenant.name} size="small" />}
        >
          {tenant.name}
        </Menu.Item>
      )}
    </Link>
  );
});

export const Header = () => {
  const { branding } = useTenantContext();
  const { tenantId } = useParams({ from: '/$tenantId' });
  const { logout } = useAuth();
  const { bypassAuth } = useAuthContext();
  const { data: tenants } = useListUserTenantsQuery();

  const currentTenant = tenants?.find((curr) => curr.id === tenantId);

  const applicationIcon = branding?.logoUrl ? (
    <img src={branding.logoUrl} width={36} height={36} alt="logo" />
  ) : (
    <IconSema4 size={36} />
  );

  return (
    <Box
      as="header"
      display="flex"
      alignItems="center"
      className={cn('h-16 px-6', 'border-b border-solid border-b-gray-200')}
    >
      <Menu
        trigger={
          <Box
            display="flex"
            gap="$8"
            alignItems="center"
            justifyContent="space-between"
            as="button"
            backgroundColor="transparent"
            color="content.primary"
          >
            {applicationIcon}
            {currentTenant?.name}
            <IconChevronDown />
          </Box>
        }
        placement="bottom-end"
        initialFocus={1}
      >
        {tenants?.map((tenant) => <MenuItem tenant={tenant} key={tenant.id} />)}

        <Divider />

        {!bypassAuth && (
          <Menu.Item
            icon={IconLogOut}
            onClick={() => logout({ returnTo: `${window.location.origin}/signout-callback` })}
          >
            Log out
          </Menu.Item>
        )}
      </Menu>
    </Box>
  );
};
