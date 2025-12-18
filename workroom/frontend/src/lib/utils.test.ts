import { describe, it, expect, vi } from 'vitest';

// Mock the router import as it causes test run fails due to bringing in the whole frontend stack where ESM related imports fail to resolve with vitest
vi.mock('~/components/providers/Router', () => ({
  router: {
    flatRoutes: [],
  },
}));

import { getTenantWorkoomRedirect } from './utils';

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
