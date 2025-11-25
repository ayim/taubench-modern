/**
 * Shared constants for extraction file names and aria labels
 * Prevents duplication of magic strings across components
 */

export const EXTRACTION_FILE_NAMES = {
  SCHEMA: 'extraction_schema.json',
  DATA: 'extracted_data.json',
} as const;

export const EXTRACTION_ARIA_LABELS = {
  SCHEMA: 'extraction-schema-json',
  DATA: 'extracted-data-json',
} as const;
