import { describe, it, expect } from 'vitest';
import {
  getCachedCredentials,
  CACHED_CREDENTIALS_BUFFER_IN_SECONDS,
  ROLE_ASSUME_DURATION_IN_SECONDS,
} from './s3Client.js';

describe('hasCachedCredentials', () => {
  it('returns null when no cached credentials', () => {
    const nonCachedCredentials = null;
    const cachedCredentials = getCachedCredentials({
      roleAssumeDurationInSeconds: ROLE_ASSUME_DURATION_IN_SECONDS,
      bufferTimeInSeconds: CACHED_CREDENTIALS_BUFFER_IN_SECONDS,
      cachedCredentials: nonCachedCredentials,
    });
    expect(cachedCredentials).toEqual(null);
  });

  it('returns null when the credentials have expired a long time ago', () => {
    const expiredCredentials = {
      assumedAtMs: 1760338727736,
      credentials: {
        AccessKeyId: 'TEST_NOT_USED',
        SecretAccessKey: 'TEST_NOT_USED',
        SessionToken: 'TEST_NOT_USED',
      },
    };
    const cachedCredentials = getCachedCredentials({
      roleAssumeDurationInSeconds: ROLE_ASSUME_DURATION_IN_SECONDS,
      bufferTimeInSeconds: CACHED_CREDENTIALS_BUFFER_IN_SECONDS,
      cachedCredentials: expiredCredentials,
    });

    expect(cachedCredentials).toEqual(null);
  });

  it(`returns null when the credentials were last assumed ${ROLE_ASSUME_DURATION_IN_SECONDS}s ago`, () => {
    const expiredCredentials = {
      assumedAtMs: Date.now() - ROLE_ASSUME_DURATION_IN_SECONDS * 1000,
      credentials: {
        AccessKeyId: 'TEST_NOT_USED',
        SecretAccessKey: 'TEST_NOT_USED',
        SessionToken: 'TEST_NOT_USED',
      },
    };
    const cachedCredentials = getCachedCredentials({
      roleAssumeDurationInSeconds: ROLE_ASSUME_DURATION_IN_SECONDS,
      bufferTimeInSeconds: CACHED_CREDENTIALS_BUFFER_IN_SECONDS,
      cachedCredentials: expiredCredentials,
    });

    expect(cachedCredentials).toEqual(null);
  });

  it('returns null when the assume session is about to expire', () => {
    const expiryWithinBuffer = CACHED_CREDENTIALS_BUFFER_IN_SECONDS - 20;

    if (expiryWithinBuffer < 0) {
      throw Error(`Invalid test: the expiry should be within the buffer: ${CACHED_CREDENTIALS_BUFFER_IN_SECONDS}`);
    }

    const withinTheExpiryTreshold = Date.now() - ROLE_ASSUME_DURATION_IN_SECONDS * 1000 + expiryWithinBuffer * 1000;

    const expiredCredentials = {
      assumedAtMs: withinTheExpiryTreshold,
      credentials: {
        AccessKeyId: 'TEST_NOT_USED',
        SecretAccessKey: 'TEST_NOT_USED',
        SessionToken: 'TEST_NOT_USED',
      },
    };
    const cachedCredentials = getCachedCredentials({
      roleAssumeDurationInSeconds: ROLE_ASSUME_DURATION_IN_SECONDS,
      bufferTimeInSeconds: CACHED_CREDENTIALS_BUFFER_IN_SECONDS,
      cachedCredentials: expiredCredentials,
    });

    expect(cachedCredentials).toEqual(null);
  });

  it('returns the cached credentials when they are not YET expired', () => {
    const expiryOutsideOfBuffer = CACHED_CREDENTIALS_BUFFER_IN_SECONDS + 20;

    if (expiryOutsideOfBuffer < CACHED_CREDENTIALS_BUFFER_IN_SECONDS) {
      throw Error(`Invalid test: the expiry should be within the buffer: ${CACHED_CREDENTIALS_BUFFER_IN_SECONDS}`);
    }

    const beforeTheExpiryThreshold = Date.now() - ROLE_ASSUME_DURATION_IN_SECONDS * 1000 + expiryOutsideOfBuffer * 1000;

    const nonExpiredCredentials = {
      assumedAtMs: beforeTheExpiryThreshold,
      credentials: {
        AccessKeyId: 'TEST_NOT_USED',
        SecretAccessKey: 'TEST_NOT_USED',
        SessionToken: 'TEST_NOT_USED',
      },
    };
    const cachedCredentials = getCachedCredentials({
      roleAssumeDurationInSeconds: ROLE_ASSUME_DURATION_IN_SECONDS,
      bufferTimeInSeconds: CACHED_CREDENTIALS_BUFFER_IN_SECONDS,
      cachedCredentials: nonExpiredCredentials,
    });

    expect(cachedCredentials).toEqual(nonExpiredCredentials);
  });

  it('returns the credentials', () => {
    const validCredentials = {
      assumedAtMs: Date.now(),
      credentials: {
        AccessKeyId: 'TEST_NOT_USED',
        SecretAccessKey: 'TEST_NOT_USED',
        SessionToken: 'TEST_NOT_USED',
      },
    };
    const cachedCredentials = getCachedCredentials({
      roleAssumeDurationInSeconds: ROLE_ASSUME_DURATION_IN_SECONDS,
      bufferTimeInSeconds: CACHED_CREDENTIALS_BUFFER_IN_SECONDS,
      cachedCredentials: validCredentials,
    });

    expect(cachedCredentials).toEqual(validCredentials);
  });
});
