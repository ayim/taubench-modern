/**
 * Bounding box transformation utilities
 * Converts parse/extract data into renderable bounding box coordinates
 */

import { calculateReactPdfCoordinates, isBoxContained } from './coordinateCalculations';

export interface BoundingBox {
  fieldId: string;
  coords: { left: number; top: number; width: number; height: number };
  fieldName: string;
  fieldValue: string;
  isMatched?: boolean;
  isParentBox?: boolean;
  type?: string;
  confidence?: string;
}

/**
 * Transform parse data (result.chunks[].blocks[]) into bounding boxes for a specific page
 */
export function parseDataToBoundingBoxes(
  parseData: Record<string, unknown>,
  pageNumber: number,
  pageWidth: number,
  pageHeight: number,
  scale: number,
): BoundingBox[] {
  const boundingBoxes: BoundingBox[] = [];

  // Validate parse data structure: result.chunks
  const result = parseData?.result as Record<string, unknown> | undefined;
  if (!result?.chunks || !Array.isArray(result.chunks)) {
    return boundingBoxes;
  }

  const chunks = result.chunks as Array<{
    content?: string;
    bbox?: { left?: number; top?: number; width?: number; height?: number; page?: number };
    blocks?: Array<{
      content?: string;
      bbox?: { left?: number; top?: number; width?: number; height?: number; page?: number };
      type?: string;
      confidence?: string;
    }>;
    type?: string;
    confidence?: string;
  }>;

  // Process each chunk
  chunks.forEach((chunk, chunkIndex) => {
    // Use chunk content as the field value
    const fieldValue = chunk.content || '';

    // Skip empty chunks
    if (!fieldValue.trim()) {
      return;
    }

    // Process blocks within the chunk
    if (chunk.blocks && Array.isArray(chunk.blocks)) {
      chunk.blocks.forEach((block, blockIndex) => {
        // Check if block has bounding box data
        const { bbox } = block;
        if (!bbox) return;

        // Use block's page, or inherit from chunk if block doesn't have page
        const blockPage = bbox.page ?? chunk.bbox?.page ?? pageNumber;

        // Filter by current page
        if (blockPage !== pageNumber) return;

        // Extract field name from block content or use chunk content
        const fieldName = block.content || chunk.content || `parse_field_${chunkIndex}_${blockIndex}`;

        // Skip empty field names
        if (!fieldName.trim()) return;

        // Get raw coordinates (typically normalized 0-1)
        let coords = {
          left: bbox.left || 0,
          top: bbox.top || 0,
          width: bbox.width || 0,
          height: bbox.height || 0,
        };

        // Add padding to all bounding boxes for better readability
        const padding = 0.003; // 0.3% padding on all sides
        coords = {
          left: Math.max(0, coords.left - padding),
          top: Math.max(0, coords.top - padding),
          width: Math.min(1, coords.width + padding * 2),
          height: Math.min(1, coords.height + padding * 2),
        };

        // Fine-tune table positioning to eliminate gaps
        if (block.type?.toLowerCase() === 'table') {
          // Additional padding for tables (on top of existing padding)
          coords = {
            left: Math.max(0, coords.left - 0.005),
            top: Math.max(0, coords.top - 0.005),
            width: Math.min(1, coords.width + 0.01),
            height: Math.min(1, coords.height + 0.01),
          };
        }

        // Skip boxes with zero dimensions AFTER padding
        if (coords.width <= 0 || coords.height <= 0) return;

        // Convert to screen coordinates
        const screenCoords = calculateReactPdfCoordinates({ ...coords, page: blockPage }, pageWidth, pageHeight, scale);

        if (screenCoords) {
          boundingBoxes.push({
            fieldId: `parse-${chunkIndex}-${blockIndex}`,
            coords: screenCoords,
            fieldName,
            fieldValue: String(fieldValue),
            isMatched: false,
            isParentBox: false,
            type: block.type || 'Text',
            confidence: block.confidence || 'high',
          });
        }
      });
    }
  });

  // Sort by area (largest first) so larger boxes render behind smaller ones
  const sortedBoxes = [...boundingBoxes].sort((a, b) => {
    const areaA = a.coords.width * a.coords.height;
    const areaB = b.coords.width * b.coords.height;
    return areaB - areaA;
  });

  return sortedBoxes;
}

/**
 * Transform extracted data citations into bounding boxes for a specific page
 */
export function extractDataToBoundingBoxes(
  extractedData: Record<string, unknown>,
  pageNumber: number,
  pageWidth: number,
  pageHeight: number,
  scale: number,
): BoundingBox[] {
  const boundingBoxes: BoundingBox[] = [];

  if (!extractedData?.citations) {
    return boundingBoxes;
  }

  const citations = extractedData.citations as Record<string, unknown>;

  // Helper function to recursively extract all citation objects with bbox data
  const extractAllCitations = (
    obj: unknown,
    currentPath: string = '',
  ): Array<{ citation: Record<string, unknown>; path: string; fieldName: string }> => {
    const results: Array<{ citation: Record<string, unknown>; path: string; fieldName: string }> = [];

    if (!obj || typeof obj !== 'object') return results;

    // Check if this object is a citation (has bbox and content)
    if ('bbox' in obj && 'content' in obj) {
      // Simple field name extraction (can be enhanced)
      const fieldName = currentPath.split('.').pop() || currentPath;
      results.push({ citation: obj as Record<string, unknown>, path: currentPath, fieldName });
      return results;
    }

    // If it's an array, process each item
    if (Array.isArray(obj)) {
      obj.forEach((item, index) => {
        results.push(...extractAllCitations(item, `${currentPath}[${index}]`));
      });
    } else {
      // If it's an object, process each property
      Object.entries(obj).forEach(([key, value]) => {
        const newPath = currentPath ? `${currentPath}.${key}` : key;
        results.push(...extractAllCitations(value, newPath));
      });
    }

    return results;
  };

  // Extract all citations from the citations object
  const allCitations = extractAllCitations(citations);

  // Process each citation
  allCitations.forEach(({ citation, path, fieldName }, index) => {
    const bbox = citation.bbox as { left: number; top: number; width?: number; height?: number; page?: number };
    const content = citation.content as string;

    if (bbox && bbox.page === pageNumber) {
      const screenCoords = calculateReactPdfCoordinates(bbox, pageWidth, pageHeight, scale);

      if (screenCoords) {
        // Use path-based ID for better mapping to extracted blocks
        const fieldId = `citation-${path}-${index}`;

        boundingBoxes.push({
          fieldId,
          coords: screenCoords,
          fieldName,
          fieldValue: content,
          isMatched: false, // No matching logic in simplified version
          confidence: (citation as { confidence?: string }).confidence || 'high',
        });
      }
    }
  });

  return boundingBoxes;
}

/**
 * Deduplicate bounding boxes with identical coordinates
 * Only keeps the first occurrence
 */
export function deduplicateBoundingBoxes(boxes: BoundingBox[]): BoundingBox[] {
  return boxes.filter((box, index) => {
    // Check if this box has the same coords as any previous box
    const previousBoxes = boxes.slice(0, index);
    const isDuplicate = previousBoxes.some(
      (otherBox) =>
        box.coords.left === otherBox.coords.left &&
        box.coords.top === otherBox.coords.top &&
        box.coords.width === otherBox.coords.width &&
        box.coords.height === otherBox.coords.height,
    );
    return !isDuplicate;
  });
}

/**
 * Detect parent/child relationships in overlapping bounding boxes
 * Marks boxes that contain other boxes as parent boxes
 */
export function markParentBoxes(boxes: BoundingBox[]): BoundingBox[] {
  return boxes.map((box, index) => {
    // Check if this box contains other boxes
    const otherBoxes = boxes.filter((_, i) => i !== index);
    const isParentBox = otherBoxes.some((otherBox) => {
      return isBoxContained(otherBox.coords, box.coords);
    });

    return {
      ...box,
      isParentBox,
    };
  });
}
