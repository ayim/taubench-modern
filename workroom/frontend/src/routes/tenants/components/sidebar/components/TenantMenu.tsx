import { Box, ButtonBase, Menu, Typography } from '@sema4ai/components';
import { IconChevronDown } from '@sema4ai/icons';
import { IconSema4 } from '@sema4ai/icons/logos';
import { styled } from '@sema4ai/theme';
import { useParams } from '@tanstack/react-router';

import { RouterMenuLink } from '~/components/RouterLink';
import { useTenantContext } from '~/lib/tenantContext';
import { getTenantWorkoomRedirect } from '~/lib/utils';
import { useListUserTenantsQuery, UserTenant } from '~/queries/tenants';

const Trigger = styled(ButtonBase)`
  .styled-container {
    padding-left: 0px;
  }
`;

export const TenantMenu = () => {
  const { branding } = useTenantContext();
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });
  const { data: tenants } = useListUserTenantsQuery();

  const currentTenant = tenants?.find((curr) => curr.id === tenantId);

  const onTenantSwitch = (tenant: UserTenant) => () => {
    const workroomRedirect = getTenantWorkoomRedirect({
      tenant,
      location: window.location,
    });

    if (workroomRedirect) {
      window.location.href = workroomRedirect.href;
      return;
    }
  };

  const applicationIcon = branding?.logoUrl ? (
    <img src={branding.logoUrl} width={36} height={36} alt="logo" />
  ) : (
    <IconSema4 size={36} />
  );

  return (
    <Box>
      <Menu
        trigger={
          <Trigger>
            {applicationIcon}
            <Box maxWidth={96} px="$8" overflow="hidden">
              <Typography $nowrap truncate>
                {currentTenant?.name}a sdaksjd kjas kd aks dkas dkajsd
              </Typography>
            </Box>
            <IconChevronDown />
          </Trigger>
        }
      >
        {tenants?.map((tenant) => (
          <RouterMenuLink
            to="/tenants/$tenantId/home"
            onClick={onTenantSwitch(tenant)}
            params={{ tenantId: tenant.id }}
            key={tenant.id}
          >
            {tenant.name}
          </RouterMenuLink>
        ))}
      </Menu>
    </Box>
  );
};
