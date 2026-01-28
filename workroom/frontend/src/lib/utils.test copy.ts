import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { formatRelativeTime } from './utils';

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
