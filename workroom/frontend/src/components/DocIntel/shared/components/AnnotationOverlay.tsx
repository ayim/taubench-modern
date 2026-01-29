import { Box } from '@sema4ai/components';
import { FC, useState, useEffect } from 'react';
import { CitationBox } from './CitationBox';
import { isBoxContained, parseDataToBoundingBoxes, extractDataToBoundingBoxes } from '../utils';

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
        // Utility function that correctly handles result.chunks[].blocks[] structure
        const parseBoundingBoxes = parseDataToBoundingBoxes(parseData, pageNumber, pageWidth, pageHeight, scale);

        parseBoundingBoxes.forEach((bbox) => {
          newCitationCoords.push({
            fieldId: bbox.fieldId,
            coords: bbox.coords,
            fieldName: bbox.fieldName,
            fieldValue: bbox.fieldValue,
            isMatched: false,
            numericId: null,
            isParentBox: bbox.isParentBox,
            type: bbox.type,
            confidence: bbox.confidence,
          });
        });
      } else if (extractedData?.citations) {
        // Utility function that handles extractedData.citations structure
        const extractBoundingBoxes = extractDataToBoundingBoxes(
          extractedData,
          pageNumber,
          pageWidth,
          pageHeight,
          scale,
        );

        extractBoundingBoxes.forEach((bbox) => {
          newCitationCoords.push({
            fieldId: bbox.fieldId,
            coords: bbox.coords,
            fieldName: bbox.fieldName,
            fieldValue: bbox.fieldValue,
            isMatched: true,
            numericId: null,
            isParentBox: bbox.isParentBox,
            confidence: bbox.confidence,
          });
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
