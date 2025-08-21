import { UserTenant } from '~/queries/tenants';
import { getBasePath } from '~/utils/base';

const dateTimeFormatter = new Intl.DateTimeFormat('en-US', {
  year: 'numeric',
  month: 'long',
  day: 'numeric',
  hour: 'numeric',
  minute: 'numeric',
  hour12: true,
});

export const formatDate = (dateString: string) => {
  const date = new Date(dateString);
  const month = date.toLocaleDateString('en-US', { month: 'short' });
  const day = date.getDate();
  const year = date.getFullYear();
  const hour = date.getHours();
  const minute = date.getMinutes();
  const ampm = hour >= 12 ? 'PM' : 'AM';
  const displayHour = hour % 12 || 12;
  const displayMinute = minute.toString().padStart(2, '0');

  return `${month} ${day}, ${year} at ${displayHour}:${displayMinute} ${ampm}`;
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

  const relativeLocal = new URL(
    tenant.environment.url,
    `${window.location.protocol}//${window.location.host}`,
  ).toString();
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

export const beautifyLabel = (value: string): string => {
  const id = value.split(':')[1] || value;
  return id
    .replace(/-/g, ' ')
    .replace(/^gpt /, 'GPT ')
    .replace(/^o(\d)/i, (_, d) => `O${d} `)
    .replace(/\bmini\b/i, 'Mini')
    .replace(/\bhigh\b/i, 'High')
    .replace(/\bopenai service\b/i, 'OpenAI Service')
    .replace(/\bamazon bedrock\b/i, 'Amazon Bedrock')
    .replace(/\bazure\b/i, 'Azure')
    .replace(/\bopenai\b/i, 'OpenAI')
    .replace(/\bbedrock\b/i, 'Bedrock')
    .replace(/\b(\w)/g, (m) => m.toUpperCase());
};

export const joinURL = (...parts: Array<string>): string => {
  return parts
    .join('/')
    .replace(/[/]+/g, '/')
    .replace(/^(.+):\//, '$1://')
    .replace(/^file:/, 'file:/')
    .replace(/\/(\?|&|#[^!])/g, '$1')
    .replace(/\?/g, '&')
    .replace('&', '?');
};

export const resolveWorkroomURL = (
  path: string,
  baseUrl: string = `${window.location.protocol}//${window.location.host}`,
): string => joinURL(baseUrl, getBasePath(), path);
