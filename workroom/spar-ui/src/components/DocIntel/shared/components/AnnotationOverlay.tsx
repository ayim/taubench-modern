import { Box } from '@sema4ai/components';
import { FC, useState, useEffect } from 'react';
import { CitationBox } from './CitationBox';
import { formatFieldName, isBoxContained, calculateReactPdfCoordinates } from '../utils';

// Convert parse result to bounding boxes for visualization
// NOTE: This is a simplified version for flat parseData.chunks structure
const convertParseResultToBoundingBoxes = (
  parseData: Record<string, unknown>,
  pageNumber: number,
): Array<{
  fieldId: string;
  coords: { left: number; top: number; width: number; height: number; page?: number };
  fieldName: string;
  fieldValue: string;
  numericId: number | null;
  type?: string;
  confidence?: string;
}> => {
  const bboxes: Array<{
    fieldId: string;
    coords: { left: number; top: number; width: number; height: number; page?: number };
    fieldName: string;
    fieldValue: string;
    numericId: number | null;
    type?: string;
    confidence?: string;
  }> = [];

  // Extract chunks from parse data
  const chunks = (parseData?.chunks as Array<Record<string, unknown>>) || [];

  chunks.forEach((chunk, index) => {
    const bbox = chunk.bbox as
      | { left: number; top: number; width?: number; height?: number; page?: number }
      | undefined;
    const page = chunk.page as number | undefined;
    const type = chunk.type as string | undefined;
    const confidence = chunk.confidence as string | undefined;
    const content = chunk.content as string | undefined;

    // Only include chunks for the current page with valid bbox dimensions
    if (bbox && page === pageNumber && bbox.width !== undefined && bbox.height !== undefined) {
      bboxes.push({
        fieldId: `parse-${page}-${index}`,
        coords: {
          left: bbox.left,
          top: bbox.top,
          width: bbox.width,
          height: bbox.height,
          page: bbox.page,
        },
        fieldName: type || 'text',
        fieldValue: content || '',
        numericId: null,
        type,
        confidence,
      });
    }
  });

  return bboxes;
};

export interface AnnotationOverlayProps {
  pageNumber: number;
  pageWidth: number;
  pageHeight: number;
  scale: number;
  extractedData: Record<string, unknown> | null;
  parseData: Record<string, unknown> | null;
  showingParseBoxes: boolean;
  selectedFieldId: string | null;
  setSelectedFieldId: (fieldId: string | null) => void;
}

export const AnnotationOverlay: FC<AnnotationOverlayProps> = ({
  pageNumber,
  pageWidth,
  pageHeight,
  scale,
  extractedData,
  parseData,
  showingParseBoxes,
  selectedFieldId,
  setSelectedFieldId,
}) => {
  const [citationCoords, setCitationCoords] = useState<
    Array<{
      fieldId: string;
      coords: { left: number; top: number; width: number; height: number };
      fieldName: string;
      fieldValue: string;
      isOverlapping?: boolean;
      isMatched?: boolean;
      isParentBox?: boolean;
      numericId?: number | null;
      type?: string;
      confidence?: string;
    }>
  >([]);

  // Handle citation box click
  const handleCitationClick = (fieldId: string) => {
    // Toggle selection
    const newSelectedId = selectedFieldId === fieldId ? null : fieldId;
    setSelectedFieldId(newSelectedId);
  };

  // Calculate citation coordinates from extractedData.citations or parseData
  useEffect(() => {
    const calculateCitationCoords = () => {
      const newCitationCoords: Array<{
        fieldId: string;
        coords: { left: number; top: number; width: number; height: number };
        fieldName: string;
        fieldValue: string;
        isMatched?: boolean;
        numericId?: number | null;
        isParentBox?: boolean;
        type?: string;
        confidence?: string;
      }> = [];

      // If showing parse boxes and we have parse data, use parse bounding boxes
      if (showingParseBoxes && parseData) {
        const parseBoundingBoxes = convertParseResultToBoundingBoxes(parseData, pageNumber);

        // Sort parse bounding boxes by area (largest first) so larger boxes render behind smaller ones
        const sortedParseBoxes = [...parseBoundingBoxes].sort((a, b) => {
          const areaA = a.coords.width! * a.coords.height!;
          const areaB = b.coords.width! * b.coords.height!;
          return areaB - areaA;
        });

        sortedParseBoxes.forEach((bbox) => {
          const screenCoords = calculateReactPdfCoordinates(bbox.coords, pageWidth, pageHeight, scale);

          if (screenCoords) {
            newCitationCoords.push({
              fieldId: bbox.fieldId,
              coords: screenCoords,
              fieldName: bbox.fieldName,
              fieldValue: bbox.fieldValue,
              isMatched: false,
              numericId: bbox.numericId,
              isParentBox: false,
              type: bbox.type,
              confidence: bbox.confidence,
            });
          }
        });
      } else if (extractedData?.citations) {
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
            const fieldName = formatFieldName(currentPath);
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
        allCitations.forEach(({ citation, fieldName }, index) => {
          const bbox = citation.bbox as { left: number; top: number; width?: number; height?: number; page?: number };
          const content = citation.content as string;

          if (bbox && bbox.page === pageNumber) {
            const screenCoords = calculateReactPdfCoordinates(bbox, pageWidth, pageHeight, scale);

            if (screenCoords) {
              const fieldId = `citation-${pageNumber}-${index}`;

              newCitationCoords.push({
                fieldId,
                coords: screenCoords,
                fieldName,
                fieldValue: content,
                isMatched: true,
                numericId: null,
                confidence: (citation as { confidence?: string }).confidence || 'high',
              });
            }
          }
        });
      }

      // Deduplicate citations with identical bbox values
      const uniqueCitations = newCitationCoords.filter((citation, index) => {
        const previousCitations = newCitationCoords.slice(0, index);
        const isDuplicate = previousCitations.some(
          (otherCitation) =>
            citation.coords.left === otherCitation.coords.left &&
            citation.coords.top === otherCitation.coords.top &&
            citation.coords.width === otherCitation.coords.width &&
            citation.coords.height === otherCitation.coords.height,
        );
        return !isDuplicate;
      });

      // Detect overlapping citation boxes and determine parent/child relationships
      const processedCitations = uniqueCitations.map((citation, index) => {
        const otherCitations = uniqueCitations.filter((_, i) => i !== index);
        const isParentBox = otherCitations.some((otherCitation) => {
          const thisBox = citation.coords;
          const otherBox = otherCitation.coords;
          return isBoxContained(otherBox, thisBox);
        });

        return {
          ...citation,
          isOverlapping: isParentBox,
          isParentBox,
        };
      });

      setCitationCoords(processedCitations);
    };

    calculateCitationCoords();
  }, [pageNumber, pageWidth, pageHeight, scale, extractedData, parseData, showingParseBoxes]);

  return (
    <Box
      style={{
        pointerEvents: 'none',
        width: pageWidth,
        height: pageHeight,
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
      }}
    >
      <Box style={{ transition: 'opacity 0.3s ease-in-out' }}>
        {citationCoords.map(({ fieldId, coords, fieldName, fieldValue, isMatched, isParentBox, type, confidence }) => (
          <Box key={`citation-overlay-${fieldId}`} style={{ pointerEvents: 'auto' }}>
            <CitationBox
              coords={coords}
              fieldName={fieldName}
              fieldValue={fieldValue}
              fieldId={fieldId}
              selectedFieldId={selectedFieldId}
              onBoxClick={handleCitationClick}
              onHoverChange={() => {}}
              isMatched={isMatched}
              isParentBox={isParentBox}
              isParseBox={showingParseBoxes}
              type={type}
              confidence={confidence}
            />
          </Box>
        ))}
      </Box>
    </Box>
  );
};
