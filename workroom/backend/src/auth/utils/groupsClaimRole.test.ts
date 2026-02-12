import { describe, expect, it, vi } from 'vitest';
import { extractRoleFromOIDCGroupsClaim } from './groupsClaimRole.js';
import type { Configuration } from '../../configuration.js';
import type { OIDCTokenClaims } from '../../interfaces.js';
import type { MonitoringContext } from '../../monitoring/index.js';

describe('extractRoleFromOIDCGroupsClaim', () => {
  const createMockMonitoring = (): MonitoringContext => ({
    logger: {
      debug: vi.fn(),
      error: vi.fn(),
      info: vi.fn(),
    },
  });

  const createBaseClaims = (): OIDCTokenClaims => ({
    iss: 'https://auth.example.com',
    sub: 'user-123',
    aud: 'client-id',
    iat: Math.floor(Date.now() / 1000),
    exp: Math.floor(Date.now() / 1000) + 3600,
  });

  const createOIDCConfiguration = (oidcGroupsClaim: string): Pick<Configuration, 'auth'> => ({
    auth: {
      autoPromoteEmails: [],
      clientId: 'client-id',
      clientSecret: 'client-secret',
      intermediaryCallbackRedirectUrl: null,
      oidcGroupsClaim,
      oidcServer: 'https://auth.example.com',
      organizationAuthParam: null,
      scopes: ['openid'],
      tokenIssuer: 'https://auth.example.com',
      type: 'oidc',
    },
  });

  describe('non-oidc auth', () => {
    it('returns null when auth type is snowflake', () => {
      const monitoring = createMockMonitoring();
      const claims = { ...createBaseClaims(), groups: ['admin'] };
      const configuration: Pick<Configuration, 'auth'> = {
        auth: {
          autoPromoteEmails: [],
          tokenIssuer: '',
          type: 'snowflake',
        },
      };

      const result = extractRoleFromOIDCGroupsClaim({ monitoring, configuration }, { claims });

      expect(result).toBeNull();
    });
  });

  describe('default groups claim', () => {
    it('extracts role from "groups" claim when present', () => {
      const monitoring = createMockMonitoring();
      const claims = { ...createBaseClaims(), groups: ['admin'] };

      const result = extractRoleFromOIDCGroupsClaim(
        { monitoring, configuration: createOIDCConfiguration('groups') },
        { claims },
      );

      expect(result).toBe('admin');
    });

    it('returns null when groups claim is not present', () => {
      const monitoring = createMockMonitoring();
      const claims = createBaseClaims();

      const result = extractRoleFromOIDCGroupsClaim(
        { monitoring, configuration: createOIDCConfiguration('groups') },
        { claims },
      );

      expect(result).toBeNull();
      expect(monitoring.logger.debug).toHaveBeenCalledWith('No groups claim found in OIDC token', {
        oidcGroupsClaimName: 'groups',
      });
    });
  });

  describe('custom oidcGroupsClaim', () => {
    it('extracts role from custom claim', () => {
      const monitoring = createMockMonitoring();
      const claims = { ...createBaseClaims(), roles: ['admin'] };

      const result = extractRoleFromOIDCGroupsClaim(
        { monitoring, configuration: createOIDCConfiguration('roles') },
        { claims },
      );

      expect(result).toBe('admin');
    });

    it('returns null when custom claim is not present', () => {
      const monitoring = createMockMonitoring();
      const claims = createBaseClaims();

      const result = extractRoleFromOIDCGroupsClaim(
        { monitoring, configuration: createOIDCConfiguration('roles') },
        { claims },
      );

      expect(result).toBeNull();
      expect(monitoring.logger.debug).toHaveBeenCalledWith('No groups claim found in OIDC token', {
        oidcGroupsClaimName: 'roles',
      });
    });

    it('returns null when custom claim is empty', () => {
      const monitoring = createMockMonitoring();
      const claims = { ...createBaseClaims(), roles: [] };

      const result = extractRoleFromOIDCGroupsClaim(
        { monitoring, configuration: createOIDCConfiguration('roles') },
        { claims },
      );

      expect(result).toBeNull();
    });
  });

  describe('role priority', () => {
    it('returns admin when admin is in groups', () => {
      const monitoring = createMockMonitoring();
      const claims = { ...createBaseClaims(), groups: ['admin'] };

      const result = extractRoleFromOIDCGroupsClaim(
        { monitoring, configuration: createOIDCConfiguration('groups') },
        { claims },
      );

      expect(result).toBe('admin');
    });

    it('returns knowledgeWorker when knowledgeWorker is in groups', () => {
      const monitoring = createMockMonitoring();
      const claims = { ...createBaseClaims(), groups: ['knowledgeWorker'] };

      const result = extractRoleFromOIDCGroupsClaim(
        { monitoring, configuration: createOIDCConfiguration('groups') },
        { claims },
      );

      expect(result).toBe('knowledgeWorker');
    });

    it('returns admin when both admin and knowledgeWorker are present', () => {
      const monitoring = createMockMonitoring();
      const claims = { ...createBaseClaims(), groups: ['knowledgeWorker', 'admin'] };

      const result = extractRoleFromOIDCGroupsClaim(
        { monitoring, configuration: createOIDCConfiguration('groups') },
        { claims },
      );

      expect(result).toBe('admin');
    });
  });

  describe('dropped groups logging', () => {
    it('logs dropped groups when no valid roles match', () => {
      const monitoring = createMockMonitoring();
      const claims = { ...createBaseClaims(), groups: ['viewer', 'editor'] };

      const result = extractRoleFromOIDCGroupsClaim(
        { monitoring, configuration: createOIDCConfiguration('groups') },
        { claims },
      );

      expect(result).toBeNull();
      expect(monitoring.logger.info).toHaveBeenCalledWith('Dropped non-matching groups from OIDC claim', {
        oidcDroppedGroups: 'viewer, editor',
        oidcExpectedRoles: 'admin, knowledgeWorker',
        oidcGroupsClaimName: 'groups',
        oidcReceivedGroups: 'viewer, editor',
      });
    });

    it('logs dropped groups alongside matched roles', () => {
      const monitoring = createMockMonitoring();
      const claims = { ...createBaseClaims(), groups: ['admin', 'viewer', 'other'] };

      const result = extractRoleFromOIDCGroupsClaim(
        { monitoring, configuration: createOIDCConfiguration('groups') },
        { claims },
      );

      expect(result).toBe('admin');
      expect(monitoring.logger.info).toHaveBeenCalledWith('Dropped non-matching groups from OIDC claim', {
        oidcDroppedGroups: 'viewer, other',
        oidcExpectedRoles: 'admin, knowledgeWorker',
        oidcGroupsClaimName: 'groups',
        oidcReceivedGroups: 'admin, viewer, other',
      });
    });
  });

  describe('claim value types', () => {
    it('returns null for empty array', () => {
      const monitoring = createMockMonitoring();
      const claims = { ...createBaseClaims(), groups: [] };

      const result = extractRoleFromOIDCGroupsClaim(
        { monitoring, configuration: createOIDCConfiguration('groups') },
        { claims },
      );

      expect(result).toBeNull();
    });

    it('logs info for object type', () => {
      const monitoring = createMockMonitoring();
      const claims = { ...createBaseClaims(), 'custom-claim': { role: 'admin' } };

      const result = extractRoleFromOIDCGroupsClaim(
        { monitoring, configuration: createOIDCConfiguration('custom-claim') },
        { claims },
      );

      expect(result).toBeNull();
      expect(monitoring.logger.info).toHaveBeenCalledWith('Groups claim has unexpected type', {
        oidcGroupsClaimName: 'custom-claim',
        oidcGroupsClaimType: 'object',
      });
    });

    it('logs info for boolean type', () => {
      const monitoring = createMockMonitoring();
      const claims = { ...createBaseClaims(), 'custom-claim': true };

      const result = extractRoleFromOIDCGroupsClaim(
        { monitoring, configuration: createOIDCConfiguration('custom-claim') },
        { claims },
      );

      expect(result).toBeNull();
      expect(monitoring.logger.info).toHaveBeenCalledWith('Groups claim has unexpected type', {
        oidcGroupsClaimName: 'custom-claim',
        oidcGroupsClaimType: 'boolean',
      });
    });
  });
});
