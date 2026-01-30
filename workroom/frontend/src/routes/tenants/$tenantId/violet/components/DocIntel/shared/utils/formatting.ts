/**
 * String formatting utilities for document viewer
 */

/**
 * Format field names for display
 * Removes leading/trailing dots and cleans up array notation
 */
export const formatFieldName = (path: string): string => {
  // Remove leading/trailing dots and clean up array notation
  return path
    .replace(/^\.|\.$/g, '') // Remove leading/trailing dots
    .replace(/\.\[/g, '[') // Clean up array notation
    .replace(/\[(\d+)\]/g, '[$1]'); // Ensure array indices are formatted consistently
};
