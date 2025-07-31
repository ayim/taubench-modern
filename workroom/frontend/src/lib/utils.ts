import { UserTenant } from '~/queries/tenants';

const dateTimeFormatter = new Intl.DateTimeFormat('en-US', {
  year: 'numeric',
  month: 'long',
  day: 'numeric',
  hour: 'numeric',
  minute: 'numeric',
  hour12: true,
});

export const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

export const formatDatetime = (date?: Date | string | null): string | undefined => {
  if (!date) return undefined;
  const result = dateTimeFormatter.format(new Date(date));
  return result;
};

export const getTenantEnvironmentUrl = (tenant: UserTenant): string => {
  if (/^https?:\/\//i.test(tenant.environment.url)) {
    return tenant.environment.url.endsWith('/') ? tenant.environment.url : `${tenant.environment.url}/`;
  }

  const relativeLocal = new URL(tenant.environment.url, window.location.href).toString();
  return relativeLocal.endsWith('/') ? relativeLocal : `${relativeLocal}/`;
};

const isLocalhostOrigin = (origin: string) => /^https?:\/\/(localhost|127\.0\.0\.1|0\.0\.0\.0)(:\d+)?$/i.test(origin);

export const getTenantWorkoomRedirect = ({
  tenant,
  location,
}: {
  tenant: UserTenant;
  location: Location;
}): { href: string } | null => {
  // WHY?
  // Each ACE has one Work Room / Agent version combination
  // When using the MAIN Work Room, it is possible to hit a mismatching agent server version: each tenant can be on any given ACE
  // Instead of having to go through full backward and forward compatibility
  // We point to the matching Work Room ACE URL

  const isDev = isLocalhostOrigin(location.origin);

  if (isDev) {
    return null;
  }

  if (!tenant.environment.workroom_url) {
    return null;
  }

  const isMatchingTenantWorkroom = location.origin === tenant.environment.workroom_url;

  if (isMatchingTenantWorkroom) {
    return null;
  }

  const targetWorkRoomURL = `${tenant.environment.workroom_url}${location.pathname}${location.search}${location.hash}`;

  return {
    href: targetWorkRoomURL,
  };
};
