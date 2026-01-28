import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { getConfiguration } from './configuration.js';

describe('getConfiguration', () => {
  let envVars: Record<string, string | undefined>;

  beforeEach(() => {
    envVars = { ...process.env };

    for (const key in process.env) {
      process.env[key] = undefined;
      delete process.env[key];
    }

    Object.assign(process.env, {
      NODE_ENV: 'development',
      POSTGRES_DB: 'spar',
      POSTGRES_HOST: 'localhost',
      POSTGRES_PASSWORD: 'test',
      POSTGRES_USER: 'test',
      SEMA4AI_WORKROOM_AGENT_SERVER_URL: 'http://localhost:8000',
      SEMA4AI_WORKROOM_AUTH_MODE: 'none',
      SEMA4AI_WORKROOM_PORT: '8001',
      SEMA4AI_WORKROOM_PORT_INTERNAL: '8002',
      SEMA4AI_WORKROOM_TENANT_ID: 'spar',
    });
  });

  afterEach(() => {
    for (const key in process.env) {
      process.env[key] = undefined;
      delete process.env[key];
    }

    Object.assign(process.env, envVars);
  });

  it('returns a valid configuration instance', () => {
    const configuration = getConfiguration();

    expect(configuration).toHaveProperty('auth.type', 'none');
  });
});
