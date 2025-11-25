import { createHash } from 'node:crypto';
import z from 'zod';

/**
 * Convert any string to a v5 UUID
 */
export const stringToUUID = (str: string): string => {
  // Create a hash of the namespace + string
  const hash = createHash('sha1').update(str).digest();

  // Format as UUID v5 (set version and variant bits)
  hash[6] = (hash[6] & 0x0f) | 0x50; // Version 5
  hash[8] = (hash[8] & 0x3f) | 0x80; // Variant 10

  // Convert to UUID string format
  const uuid = [
    hash.subarray(0, 4).toString('hex'),
    hash.subarray(4, 6).toString('hex'),
    hash.subarray(6, 8).toString('hex'),
    hash.subarray(8, 10).toString('hex'),
    hash.subarray(10, 16).toString('hex'),
  ].join('-');

  return z.uuid().parse(uuid);
};
