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

  const isSingleTenant = tenants?.length === 1 && currentTenant;

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
    <img src={branding.logoUrl} width={24} height={24} alt="logo" />
  ) : (
    <IconSema4 size={24} />
  );

  if (isSingleTenant) {
    return (
      <Box display="flex" alignItems="center" pl="$8" minHeight="$40">
        {applicationIcon}
        <Box pl="$8">
          <Typography variant="body-large" fontWeight="medium">
            {currentTenant.name}
          </Typography>
        </Box>
      </Box>
    );
  }

  return (
    <Box>
      <Menu
        trigger={
          <Trigger>
            {applicationIcon}
            <Box maxWidth={96} px="$8" overflow="hidden">
              <Typography variant="body-medium" fontWeight="500" $nowrap truncate>
                {currentTenant?.name}
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
