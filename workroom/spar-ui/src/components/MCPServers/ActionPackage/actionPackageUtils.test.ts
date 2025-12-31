import { describe, expect, it } from 'vitest';
import type { components } from '@sema4ai/agent-server-interface';
import {
  parseWhitelist,
  getUniqueSecretNames,
  getUniqueSecretsMap,
  agentPackageSecretsToHeaderEntries,
} from './actionPackageUtils';

type ActionSecretsConfig = components['schemas']['ActionSecretsConfig'];
type ActionSecretDefinition = components['schemas']['ActionSecretDefinition'];

const createSecretDefinition = (description?: string): ActionSecretDefinition => ({
  type: 'string',
  description: description ?? '',
});

const createSecretsConfig = (
  action: string,
  secrets?: Record<string, ActionSecretDefinition>,
): ActionSecretsConfig => ({
  action,
  action_package: 'test-package',
  secrets,
});

const createActionPackage = (
  secrets?: Record<string, ActionSecretsConfig>,
): components['schemas']['AgentPackageActionPackageMetadata'] => ({
  name: 'test-package',
  description: 'Test package description',
  version: '1.0.0',
  whitelist: '',
  icon: '',
  path: '',
  full_path: '',
  action_package_version: '1.0.0',
  secrets,
});

describe('parseWhitelist', () => {
  it.each([
    { input: '', expected: null, description: 'empty string' },
    { input: '   ', expected: null, description: 'whitespace-only string' },
    { input: ',,,   ,,,', expected: null, description: 'all items empty after filtering' },
  ])('returns null for $description', ({ input, expected }) => {
    expect(parseWhitelist(input)).toBe(expected);
  });

  it.each([
    { input: 'action1', expected: ['action1'], description: 'single item' },
    {
      input: 'action1,action2,action3',
      expected: ['action1', 'action2', 'action3'],
      description: 'multiple comma-separated items',
    },
    {
      input: '  action1  ,  action2  ',
      expected: ['action1', 'action2'],
      description: 'items with whitespace (trims)',
    },
    { input: 'action1,,action2', expected: ['action1', 'action2'], description: 'empty items from multiple commas' },
    { input: 'action1,   ,action2', expected: ['action1', 'action2'], description: 'whitespace-only items' },
  ])('parses $description', ({ input, expected }) => {
    expect(parseWhitelist(input)).toEqual(expected);
  });
});

describe('getUniqueSecretNames', () => {
  it.each([
    { secrets: undefined, description: 'secrets is undefined' },
    { secrets: {}, description: 'secrets is empty object' },
  ])('returns empty set when $description', ({ secrets }) => {
    const actionPackage = createActionPackage(secrets);
    const result = getUniqueSecretNames(actionPackage, null);
    expect(result.size).toBe(0);
  });

  it('collects secret names from single action', () => {
    const actionPackage = createActionPackage({
      action1: createSecretsConfig('action1', {
        API_KEY: createSecretDefinition('API key'),
        API_SECRET: createSecretDefinition('API secret'),
      }),
    });
    const result = getUniqueSecretNames(actionPackage, null);
    expect(result).toEqual(new Set(['API_KEY', 'API_SECRET']));
  });

  it('collects unique secret names from multiple actions', () => {
    const actionPackage = createActionPackage({
      action1: createSecretsConfig('action1', {
        API_KEY: createSecretDefinition('API key'),
        SHARED_SECRET: createSecretDefinition('Shared'),
      }),
      action2: createSecretsConfig('action2', {
        DATABASE_URL: createSecretDefinition('DB URL'),
        SHARED_SECRET: createSecretDefinition('Shared'),
      }),
    });
    const result = getUniqueSecretNames(actionPackage, null);
    expect(result).toEqual(new Set(['API_KEY', 'SHARED_SECRET', 'DATABASE_URL']));
  });

  it('filters actions by whitelist', () => {
    const actionPackage = createActionPackage({
      action1: createSecretsConfig('action1', {
        SECRET_A: createSecretDefinition('A'),
      }),
      action2: createSecretsConfig('action2', {
        SECRET_B: createSecretDefinition('B'),
      }),
      action3: createSecretsConfig('action3', {
        SECRET_C: createSecretDefinition('C'),
      }),
    });
    const result = getUniqueSecretNames(actionPackage, ['action1', 'action3']);
    expect(result).toEqual(new Set(['SECRET_A', 'SECRET_C']));
  });

  it('returns empty set when whitelist excludes all actions', () => {
    const actionPackage = createActionPackage({
      action1: createSecretsConfig('action1', {
        SECRET_A: createSecretDefinition('A'),
      }),
    });
    const result = getUniqueSecretNames(actionPackage, ['nonexistent']);
    expect(result.size).toBe(0);
  });

  it.each([
    { secrets: undefined, description: 'undefined secrets property' },
    { secrets: {}, description: 'empty secrets object' },
  ])('handles action with $description', ({ secrets }) => {
    const actionPackage = createActionPackage({
      action1: createSecretsConfig('action1', secrets),
    });
    const result = getUniqueSecretNames(actionPackage, null);
    expect(result.size).toBe(0);
  });
});

describe('getUniqueSecretsMap', () => {
  it.each([
    { secrets: undefined, description: 'secrets is undefined' },
    { secrets: {}, description: 'secrets is empty object' },
  ])('returns empty map when $description', ({ secrets }) => {
    const actionPackage = createActionPackage(secrets);
    const result = getUniqueSecretsMap(actionPackage, null);
    expect(result.size).toBe(0);
  });

  it('collects secrets with descriptions from single action', () => {
    const actionPackage = createActionPackage({
      action1: createSecretsConfig('action1', {
        API_KEY: createSecretDefinition('The API key for authentication'),
      }),
    });
    const result = getUniqueSecretsMap(actionPackage, null);
    expect(result.get('API_KEY')).toEqual({
      description: 'The API key for authentication',
      actions: ['action1'],
    });
  });

  it('collects actions that share the same secret', () => {
    const actionPackage = createActionPackage({
      action1: createSecretsConfig('action1', {
        SHARED_SECRET: createSecretDefinition('Shared secret'),
      }),
      action2: createSecretsConfig('action2', {
        SHARED_SECRET: createSecretDefinition('Shared secret'),
      }),
      action3: createSecretsConfig('action3', {
        SHARED_SECRET: createSecretDefinition('Shared secret'),
      }),
    });
    const result = getUniqueSecretsMap(actionPackage, null);
    expect(result.get('SHARED_SECRET')?.actions).toEqual(['action1', 'action2', 'action3']);
  });

  it('preserves first description when secret appears in multiple actions', () => {
    const actionPackage = createActionPackage({
      action1: createSecretsConfig('action1', {
        API_KEY: createSecretDefinition('First description'),
      }),
      action2: createSecretsConfig('action2', {
        API_KEY: createSecretDefinition('Second description'),
      }),
    });
    const result = getUniqueSecretsMap(actionPackage, null);
    expect(result.get('API_KEY')?.description).toBe('First description');
  });

  it('collects multiple different secrets correctly', () => {
    const actionPackage = createActionPackage({
      action1: createSecretsConfig('action1', {
        SECRET_A: createSecretDefinition('Secret A'),
        SECRET_B: createSecretDefinition('Secret B'),
      }),
      action2: createSecretsConfig('action2', {
        SECRET_B: createSecretDefinition('Secret B'),
        SECRET_C: createSecretDefinition('Secret C'),
      }),
    });
    const result = getUniqueSecretsMap(actionPackage, null);

    expect(result.size).toBe(3);
    expect(result.get('SECRET_A')).toEqual({ description: 'Secret A', actions: ['action1'] });
    expect(result.get('SECRET_B')).toEqual({ description: 'Secret B', actions: ['action1', 'action2'] });
    expect(result.get('SECRET_C')).toEqual({ description: 'Secret C', actions: ['action2'] });
  });

  it('filters actions by whitelist', () => {
    const actionPackage = createActionPackage({
      action1: createSecretsConfig('action1', {
        SECRET_A: createSecretDefinition('A'),
      }),
      action2: createSecretsConfig('action2', {
        SECRET_B: createSecretDefinition('B'),
      }),
    });
    const result = getUniqueSecretsMap(actionPackage, ['action1']);
    expect(result.size).toBe(1);
    expect(result.has('SECRET_A')).toBe(true);
    expect(result.has('SECRET_B')).toBe(false);
  });

  it('returns empty map when whitelist excludes all actions', () => {
    const actionPackage = createActionPackage({
      action1: createSecretsConfig('action1', {
        SECRET_A: createSecretDefinition('A'),
      }),
    });
    const result = getUniqueSecretsMap(actionPackage, ['nonexistent']);
    expect(result.size).toBe(0);
  });

  it('handles action with undefined secrets property', () => {
    const actionPackage = createActionPackage({
      action1: createSecretsConfig('action1', undefined),
    });
    const result = getUniqueSecretsMap(actionPackage, null);
    expect(result.size).toBe(0);
  });

  it('handles secret with empty description', () => {
    const actionPackage = createActionPackage({
      action1: createSecretsConfig('action1', {
        SECRET_EMPTY_DESC: { type: 'string', description: '' },
      }),
    });
    const result = getUniqueSecretsMap(actionPackage, null);
    expect(result.get('SECRET_EMPTY_DESC')).toEqual({
      description: '',
      actions: ['action1'],
    });
  });

  it('handles whitelist with partial matches', () => {
    const actionPackage = createActionPackage({
      action1: createSecretsConfig('action1', {
        SECRET_A: createSecretDefinition('A'),
        SHARED: createSecretDefinition('Shared'),
      }),
      action2: createSecretsConfig('action2', {
        SECRET_B: createSecretDefinition('B'),
        SHARED: createSecretDefinition('Shared'),
      }),
      action3: createSecretsConfig('action3', {
        SECRET_C: createSecretDefinition('C'),
        SHARED: createSecretDefinition('Shared'),
      }),
    });
    const result = getUniqueSecretsMap(actionPackage, ['action1', 'action3']);

    expect(result.size).toBe(3);
    expect(result.get('SECRET_A')?.actions).toEqual(['action1']);
    expect(result.get('SECRET_C')?.actions).toEqual(['action3']);
    expect(result.get('SHARED')?.actions).toEqual(['action1', 'action3']);
    expect(result.has('SECRET_B')).toBe(false);
  });
});

describe('agentPackageSecretsToHeaderEntries', () => {
  it.each<{ input: Record<string, string> | undefined; description: string }>([
    { input: undefined, description: 'undefined' },
    { input: {}, description: 'empty object' },
    { input: { API_KEY: '', OTHER: '' }, description: 'all empty strings' },
    { input: { API_KEY: '   ', OTHER: '  ' }, description: 'all whitespace-only' },
  ])('returns undefined for $description', ({ input }) => {
    expect(agentPackageSecretsToHeaderEntries(input)).toBeUndefined();
  });

  it('converts secrets to header entries with type secret', () => {
    const result = agentPackageSecretsToHeaderEntries({
      API_KEY: 'my-api-key',
      API_SECRET: 'my-secret',
    });
    expect(result).toEqual([
      { key: 'API_KEY', value: 'my-api-key', type: 'secret' },
      { key: 'API_SECRET', value: 'my-secret', type: 'secret' },
    ]);
  });

  it('filters out empty and whitespace-only values', () => {
    const result = agentPackageSecretsToHeaderEntries({
      VALID_KEY: 'valid-value',
      EMPTY_KEY: '',
      WHITESPACE_KEY: '   ',
      ANOTHER_VALID: 'another-value',
    });
    expect(result).toEqual([
      { key: 'VALID_KEY', value: 'valid-value', type: 'secret' },
      { key: 'ANOTHER_VALID', value: 'another-value', type: 'secret' },
    ]);
  });
});
