/**
 * Coordinate calculation utilities for PDF bounding boxes
 * Handles transformation between PDF coordinates and screen coordinates
 */

/**
 * Convert PDF coordinates to react-pdf screen coordinates
 * Handles both normalized (0-1) and absolute PDF point coordinates
 */
export function calculateReactPdfCoordinates(
  bbox: { left: number; top: number; width?: number; height?: number; page?: number },
  pageWidth: number,
  pageHeight: number,
  scale: number,
): { left: number; top: number; width: number; height: number } | null {
  try {
    const pdfLeft = bbox.left;
    const pdfTop = bbox.top;
    const pdfWidth = bbox.width || 0;
    const pdfHeight = bbox.height || 0;

    // Skip boxes with invalid dimensions
    if (pdfWidth <= 0 || pdfHeight <= 0) {
      return null;
    }

    // Check if coordinates are normalized (0-1 range)
    const isNormalized = pdfLeft <= 1 && pdfTop <= 1 && pdfWidth <= 1 && pdfHeight <= 1;

    let screenLeft: number;
    let screenTop: number;
    let screenWidth: number;
    let screenHeight: number;

    if (isNormalized) {
      // Coordinates are normalized (0-1 range) - scale to page dimensions
      // pageWidth and pageHeight are already scaled by react-pdf
      screenLeft = pdfLeft * pageWidth;
      screenTop = pdfTop * pageHeight;
      screenWidth = pdfWidth * pageWidth;
      screenHeight = pdfHeight * pageHeight;
    } else {
      // Coordinates are in PDF points - scale directly
      screenLeft = pdfLeft * scale;
      screenTop = pdfTop * scale;
      screenWidth = pdfWidth * scale;
      screenHeight = pdfHeight * scale;
    }

    return {
      left: screenLeft,
      top: screenTop,
      width: screenWidth,
      height: screenHeight,
    };
  } catch (error) {
    return null;
  }
}

/**
 * Check if one bounding box is contained within another
 * Used to detect parent/child relationships in overlapping boxes
 */
export function isBoxContained(
  innerBox: { left: number; top: number; width: number; height: number },
  outerBox: { left: number; top: number; width: number; height: number },
  threshold: number = 5, // pixels tolerance
): boolean {
  return (
    innerBox.left >= outerBox.left - threshold &&
    innerBox.top >= outerBox.top - threshold &&
    innerBox.left + innerBox.width <= outerBox.left + outerBox.width + threshold &&
    innerBox.top + innerBox.height <= outerBox.top + outerBox.height + threshold
  );
}
