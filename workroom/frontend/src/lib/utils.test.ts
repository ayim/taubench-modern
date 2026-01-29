import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { formatRelativeTime, getPublicApiEndpointUrl, getTenantWorkoomRedirect } from './utils';

// Mock the router import as it causes test run fails due to bringing in the whole frontend stack where ESM related imports fail to resolve with vitest
vi.mock('~/components/providers/Router', () => ({
  router: {
    flatRoutes: [],
  },
}));

const getLocationMock = ({
  origin,
  pathname,
  search,
  hash,
}: Pick<Window['location'], 'origin' | 'pathname' | 'search' | 'hash'>) =>
  ({
    origin,
    pathname,
    search,
    hash,
  }) as Window['location'];

describe('getTenantWorkoomRedirect', () => {
  it.each(['http://localhost:3000', 'http://127.0.0.1:3000'])('returns null in dev for %s', (origin) => {
    const workroomRedirect = getTenantWorkoomRedirect({
      tenant: {
        id: 'a0a96e3d-34fe-4f97-ae9b-75cc2d523aa8',
        name: 'CI1',
        organization: {
          id: 'ee803305-b10b-4951-beab-3b8cd7788e47',
          name: 'CI1 Platform Team',
        },
        environment: {
          id: 'bf30909a-4b7a-4faa-bf41-c47659f4dd19',
          url: 'https://ace-bf30909a.dev-ci1-ee803305.sema4ai.work',
          workroom_url: 'https://agents-ee803305.dev-ci1-ee803305.sema4ai.work',
        },
      },
      location: getLocationMock({
        origin,
        pathname: '/fc3c59e1-f592-4e3f-87e2-f4b017fb1073/home',
        search: '',
        hash: '',
      }),
    });

    expect(workroomRedirect).toBeNull();
  });

  it('returns null when tenant has no workroom_url', () => {
    const workroomRedirect = getTenantWorkoomRedirect({
      tenant: {
        id: 'e8734f71-30fe-4db8-a342-f01c804a2b8f',
        name: 'DEV CI1 ACE workspace (ex "Agents")',
        organization: {
          id: 'ee803305-b10b-4951-beab-3b8cd7788e47',
          name: 'CI1 Platform Team',
        },
        environment: {
          id: '02cf969d-769a-4db4-995d-849bcb4d0b2f',
          url: 'https://ace-02cf969d.dev-ci1-ee803305.sema4ai.work',
          workroom_url: undefined, // workroom_url is only relevant in the ACE context where an organisation can have multiple work rooms
        },
      },
      location: getLocationMock({
        origin: 'https://ace-02cf969d.dev-ci1-ee803305.sema4ai.work',
        pathname: '/',
        search: '',
        hash: '',
      }),
    });

    expect(workroomRedirect).toBeNull();
  });

  it('returns the correct redirect target for legacy ACE tenants', () => {
    const workroomRedirect = getTenantWorkoomRedirect({
      tenant: {
        id: 'a0a96e3d-34fe-4f97-ae9b-75cc2d523aa8',
        name: 'CI1',
        organization: {
          id: 'ee803305-b10b-4951-beab-3b8cd7788e47',
          name: 'CI1 Platform Team',
        },
        environment: {
          id: 'bf30909a-4b7a-4faa-bf41-c47659f4dd19',
          url: 'https://ace-bf30909a.dev-ci1-ee803305.sema4ai.work',
          workroom_url: 'https://agents-ee803305.dev-ci1-ee803305.sema4ai.work',
        },
      },
      location: getLocationMock({
        origin: 'https://ace-02cf969d.dev-ci1-ee803305.sema4ai.work',
        pathname: '/fc3c59e1-f592-4e3f-87e2-f4b017fb1073/home',
        search: '?tab=logs',
        hash: '#test-hash-value',
      }),
    });

    expect(workroomRedirect).not.toBeNull();
    expect(workroomRedirect?.href).toBe('https://agents-ee803305.dev-ci1-ee803305.sema4ai.work');
  });

  it('returns the correct redirect target for current ACE tenants', () => {
    const workroomRedirect = getTenantWorkoomRedirect({
      tenant: {
        id: 'a0a96e3d-34fe-4f97-ae9b-75cc2d523aa8',
        name: 'CI1',
        organization: {
          id: 'ee803305-b10b-4951-beab-3b8cd7788e47',
          name: 'CI1 Platform Team',
        },
        environment: {
          id: 'bf30909a-4b7a-4faa-bf41-c47659f4dd19',
          url: 'https://ace-bf30909a.dev-ci1-ee803305.sema4ai.work',
          workroom_url: 'https://agents-ee803305.dev-ci1-ee803305.sema4ai.work',
          tenant_workroom_url:
            'https://agents-ee803305.dev-ci1-ee803305.sema4ai.work/tenants/a0a96e3d-34fe-4f97-ae9b-75cc2d523aa8',
        },
      },
      location: getLocationMock({
        origin: 'https://ace-02cf969d.dev-ci1-ee803305.sema4ai.work',
        pathname: '/fc3c59e1-f592-4e3f-87e2-f4b017fb1073/home',
        search: '?tab=logs',
        hash: '#test-hash-value',
      }),
    });

    expect(workroomRedirect).not.toBeNull();
    expect(workroomRedirect?.href).toBe(
      'https://agents-ee803305.dev-ci1-ee803305.sema4ai.work/tenants/a0a96e3d-34fe-4f97-ae9b-75cc2d523aa8',
    );
  });
});

describe('getPublicApiEndpointUrl', () => {
  it.each([
    { origin: 'https://example.com', tenantId: 'abc-123', expected: 'https://example.com/tenants/abc-123/api/v1' },
    {
      origin: 'http://localhost:3000',
      tenantId: 'test-tenant',
      expected: 'http://localhost:3000/tenants/test-tenant/api/v1',
    },
  ])('returns $expected for origin=$origin and tenantId=$tenantId', ({ origin, tenantId, expected }) => {
    const result = getPublicApiEndpointUrl({ origin, tenantId });
    expect(result).toBe(expected);
  });
});

describe(formatRelativeTime.name, () => {
  const FIXED_NOW = new Date('2025-01-15T12:00:00.000Z');

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(FIXED_NOW);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('invalid inputs', () => {
    it('returns null for invalid date string', () => {
      expect(formatRelativeTime('invalid-date')).toBeNull();
    });

    it('returns null for empty string', () => {
      expect(formatRelativeTime('')).toBeNull();
    });

    it('returns null for epoch timestamp (1970)', () => {
      expect(formatRelativeTime('1970-01-01T00:00:00.000Z')).toBeNull();
    });
  });

  describe('today (same calendar day)', () => {
    it('returns "Today" for current time', () => {
      expect(formatRelativeTime('2025-01-15T12:00:00.000Z')).toBe('Today');
    });

    it('returns "Today" for 1 hour ago', () => {
      expect(formatRelativeTime('2025-01-15T11:00:00.000Z')).toBe('Today');
    });

    it('returns "Today" for earlier same day', () => {
      expect(formatRelativeTime('2025-01-15T00:00:00.000Z')).toBe('Today');
    });

    it('returns "1d ago" for yesterday even if less than 24 hours', () => {
      expect(formatRelativeTime('2025-01-14T13:00:00.000Z')).toBe('1d ago');
    });
  });

  describe('days ago', () => {
    it('returns "1d ago" for exactly 1 day ago', () => {
      expect(formatRelativeTime('2025-01-14T12:00:00.000Z')).toBe('1d ago');
    });

    it('returns "2d ago" for 2 days ago', () => {
      expect(formatRelativeTime('2025-01-13T12:00:00.000Z')).toBe('2d ago');
    });

    it('returns "6d ago" for 6 days ago', () => {
      expect(formatRelativeTime('2025-01-09T12:00:00.000Z')).toBe('6d ago');
    });
  });

  describe('weeks ago', () => {
    it('returns "1w ago" for 7 days ago', () => {
      expect(formatRelativeTime('2025-01-08T12:00:00.000Z')).toBe('1w ago');
    });

    it('returns "1w ago" for 13 days ago', () => {
      expect(formatRelativeTime('2025-01-02T12:00:00.000Z')).toBe('1w ago');
    });

    it('returns "2w ago" for 14 days ago', () => {
      expect(formatRelativeTime('2025-01-01T12:00:00.000Z')).toBe('2w ago');
    });

    it('returns "4w ago" for 29 days ago', () => {
      expect(formatRelativeTime('2024-12-17T12:00:00.000Z')).toBe('4w ago');
    });
  });

  describe('months ago', () => {
    it('returns "1mo ago" for 30 days ago', () => {
      expect(formatRelativeTime('2024-12-16T12:00:00.000Z')).toBe('1mo ago');
    });

    it('returns "1mo ago" for 59 days ago', () => {
      expect(formatRelativeTime('2024-11-17T12:00:00.000Z')).toBe('1mo ago');
    });

    it('returns "2mo ago" for 60 days ago', () => {
      expect(formatRelativeTime('2024-11-16T12:00:00.000Z')).toBe('2mo ago');
    });

    it('returns "12mo ago" for 364 days ago', () => {
      expect(formatRelativeTime('2024-01-17T12:00:00.000Z')).toBe('12mo ago');
    });
  });

  describe('years ago', () => {
    it('returns "1y ago" for 365 days ago', () => {
      expect(formatRelativeTime('2024-01-16T12:00:00.000Z')).toBe('1y ago');
    });

    it('returns "1y ago" for 729 days ago', () => {
      expect(formatRelativeTime('2023-01-17T12:00:00.000Z')).toBe('1y ago');
    });

    it('returns "2y ago" for 730 days ago', () => {
      expect(formatRelativeTime('2023-01-16T12:00:00.000Z')).toBe('2y ago');
    });

    it('returns "5y ago" for 5 years ago', () => {
      expect(formatRelativeTime('2020-01-15T12:00:00.000Z')).toBe('5y ago');
    });
  });
});
