import { Box, Button, Divider, Typography, Tooltip, Switch } from '@sema4ai/components';
import { IconArrowLeft, IconArrowRight, IconMinus, IconPlus } from '@sema4ai/icons';
import { FC, useState, useEffect, useCallback } from 'react';
import { pdfjs, Document, Page } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

import { useDocumentIntelligenceStore, ParseDocumentResponsePayload } from '../store/useDocumentIntelligenceStore';
import { formatFieldName, convertParseResultToBoundingBoxes } from '../utils/dataTransformations';

export type PDFDocumentProxy = pdfjs.PDFDocumentProxy;
export type PDFPageProxy = pdfjs.PDFPageProxy;

// Helper function to find field ID by citation content matching
const findFieldIdByContent = (fieldName: string): string | null => {
  // Get the layoutFields from the store to find matching fields
  const { layoutFields } = useDocumentIntelligenceStore.getState();

  // Search through all fields to find one that matches the citation content
  const matchingField = layoutFields.find((field) => {
    const fieldValue = field.value || '';
    return (
      fieldValue === fieldName ||
      fieldValue.includes(fieldName) ||
      fieldName.includes(fieldValue) ||
      fieldValue.toLowerCase().includes(fieldName.toLowerCase()) ||
      fieldName.toLowerCase().includes(fieldValue.toLowerCase())
    );
  });

  if (matchingField) {
    return matchingField.id;
  }
  return null;
};

// Helper function to find table row ID by content matching
const findTableRowIdByContent = (fieldName: string): string | null => {
  // Get the layoutTables from the store to find matching table rows
  const { layoutTables } = useDocumentIntelligenceStore.getState();

  // Search through all table data to find a row that contains content matching the citation content
  const allTableRows = layoutTables.flatMap((table) => (table.data || []).map((rowData) => ({ table, rowData })));

  const matchingRow = allTableRows.find(({ rowData }) => {
    const cellValues = Object.values(rowData);
    return cellValues.some(
      (value) =>
        value &&
        (value === fieldName ||
          value.includes(fieldName) ||
          fieldName.includes(value) ||
          value.toLowerCase().includes(fieldName.toLowerCase()) ||
          fieldName.toLowerCase().includes(value.toLowerCase())),
    );
  });

  if (matchingRow) {
    const rowIdentifier =
      Object.values(matchingRow.rowData).find((value) => value?.trim()) || Object.keys(matchingRow.rowData).join('-');
    return `table-row-${rowIdentifier}`;
  }

  return null;
};

// Function to scroll to a specific field in the right panel
const scrollToField = (fieldId: string) => {
  // Find the field row by data-field-id attribute
  const fieldRow = document.querySelector(`[data-field-id="${fieldId}"]`);

  if (fieldRow) {
    // Scroll the field into view with smooth behavior
    fieldRow.scrollIntoView({
      behavior: 'smooth',
      block: 'center', // Center the field in the viewport
      inline: 'nearest',
    });
  }
};

interface DocumentViewerProps {
  isReadOnly: boolean;
}

// Child bounding box component for citations
interface CitationBoxProps {
  coords: { left: number; top: number; width: number; height: number };
  fieldName: string;
  fieldValue: string;
  fieldId: string;
  selectedFieldId?: string | null;
  onBoxClick?: (fieldId: string) => void;
  onHoverChange?: (fieldId: string | null) => void;
  isMatched?: boolean; // Add flag to indicate if this citation matches a result
  isParentBox?: boolean; // Add flag to indicate if this is a parent box
  numericId?: number | null; // Add numeric ID for matching with layoutFields
  isParseBox?: boolean; // Add flag to indicate if this is a parse bounding box
  type?: string; // Add type information for parse boxes
  confidence?: string; // Add confidence information for parse boxes
}

// Child bounding box component for citations
const CitationBox: FC<CitationBoxProps> = ({
  coords,
  fieldName,
  fieldValue,
  fieldId,
  selectedFieldId,
  onBoxClick,
  onHoverChange,
  isMatched = false,
  isParentBox = false,
  numericId = null,
  isParseBox = false,
  type,
  confidence,
}) => {
  const [isHovered, setIsHovered] = useState(false);

  // Check if this citation box is selected
  const isSelected = fieldId === selectedFieldId;

  // Also check if this citation corresponds to the selected field by numeric ID
  const isSelectedByNumericId = selectedFieldId
    ? (() => {
        const { layoutFields } = useDocumentIntelligenceStore.getState();
        const selectedField = layoutFields.find((f) => f.id === selectedFieldId);
        const matches = selectedField?.citationId === numericId;
        return matches;
      })()
    : false;

  // Also check if this citation corresponds to a selected table row
  const isSelectedByTableRow = selectedFieldId
    ? (() => {
        // Check if the selectedFieldId is a table row ID (starts with "table-row-")
        if (selectedFieldId.startsWith('table-row-')) {
          // Try to match this citation with the selected table row using the actual citation content
          const matchingTableRowId = findTableRowIdByContent(fieldValue);
          const matches = matchingTableRowId === selectedFieldId;
          return matches;
        }
        return false;
      })()
    : false;

  const isActuallySelected = isSelected || isSelectedByNumericId || isSelectedByTableRow;

  // Handle citation box click to select corresponding field in right panel
  const handleBoxClick = (e: React.MouseEvent) => {
    e.stopPropagation();

    // Parent boxes are non-interactive
    if (isParentBox) return;

    // Parse boxes are non-clickable (they don't correspond to extracted fields)
    if (isParseBox) return;

    if (!onBoxClick || !fieldId) return;

    // Always call onBoxClick with the fieldId - let the parent handle the selection logic
    // The parent will determine if this should toggle or maintain selection
    onBoxClick(fieldId);
  };

  // Handle hover events to notify parent
  const handleMouseEnter = () => {
    // Parent boxes don't respond to hover
    if (isParentBox) return;

    setIsHovered(true);
    if (onHoverChange) {
      onHoverChange(fieldId);
    }
  };

  const handleMouseLeave = () => {
    // Parent boxes don't respond to hover
    if (isParentBox) return;

    setIsHovered(false);
    if (onHoverChange) {
      onHoverChange(null);
    }
  };

  const getTooltipText = () => {
    if (isParseBox && type) {
      // For parse boxes, show type and confidence information
      return (
        <span style={{ fontSize: '12px', lineHeight: '1.3' }}>
          Type: {type}
          {confidence && confidence !== 'high' && (
            <><br />Confidence: {confidence}</>
          )}
        </span>
      );
    }

    // For extract citations, show field name and value, plus confidence if low
    const cleanFieldName = fieldName.replace(/\[\d+\]/g, '');
    return (
      <span style={{ fontSize: '12px', lineHeight: '1.3' }}>
        {cleanFieldName}: {fieldValue}
        {confidence && confidence !== 'high' && (
          <><br />Confidence: {confidence}</>
        )}
      </span>
    );
  };

  const getBorderColor = () => {
    // Parent boxes are transparent and non-interactive
    if (isParentBox) return 'transparent';

    // Parse boxes use blue colors, but red for low confidence
    if (isParseBox) {
      if (confidence === 'low') {
        if (isHovered || isActuallySelected) return 'rgb(140, 24, 22)'; // Darker red on hover/selection
        return 'rgb(140, 24, 22)'; // Red border for low confidence parse boxes
      }
      if (isHovered || isActuallySelected) return 'rgb(22, 95, 140)'; // Darker blue on hover/selection
      return 'rgb(22, 95, 140)'; // Blue border for parse boxes
    }

    // Extract citations use green colors, but red for low confidence
    // Hover/selection takes highest priority
    if (isHovered || isActuallySelected) return 'rgba(255, 193, 7, 1)'; // Yellow border on hover OR when selected
    // Low confidence extract citations use red
    if (confidence === 'low') return 'rgb(140, 24, 22)'; // Red border for low confidence extract citations
    // If matched, use the specified green border
    if (isMatched) return 'rgb(22, 140, 43)'; // Green border for matched citations
    // Default green for unmatched citations
    return 'rgb(22, 140, 43)'; // Green for citation boxes
  };

  const getBackgroundColor = () => {
    // Parent boxes are transparent and non-interactive
    if (isParentBox) return 'transparent';

    // Parse boxes use blue colors, but red for low confidence
    if (isParseBox) {
      if (confidence === 'low') {
        if (isHovered || isActuallySelected) return 'rgb(238 59 25 / 40%)'; // Darker red background on hover/selection
        return 'rgb(238 59 25 / 20%)'; // Light red background for low confidence parse boxes
      }
      if (isHovered || isActuallySelected) return 'rgb(25 148 238 / 40%)'; // Darker blue background on hover/selection
      return 'rgb(25 148 238 / 20%)'; // Light blue background for parse boxes
    }

    // Extract citations use green colors, but red for low confidence
    // Hover/selection takes highest priority
    if (isHovered || isActuallySelected) return 'rgba(255, 193, 7, 0.4)'; // Yellow background on hover OR when selected
    // Low confidence extract citations use red
    if (confidence === 'low') return 'rgb(238 59 25 / 20%)'; // Light red background for low confidence extract citations
    // If matched, use the specified green background
    if (isMatched) return 'rgb(39 214 60 / 20%)'; // Green background for matched citations
    // Default green for unmatched citations
    return 'rgb(39 214 60 / 20%)'; // Green background for citation boxes
  };

  // Extract nested ternary expressions to variables
  let zIndex: number;
  if (isParentBox) {
    zIndex = 1000;
  } else if (isHovered || isActuallySelected) {
    zIndex = 2000;
  } else {
    zIndex = 1500;
  }

  let boxShadow: string;
  if (isParentBox) {
    boxShadow = 'none';
  } else if (isHovered || isActuallySelected) {
    boxShadow = '0 2px 8px rgba(0, 0, 0, 0.2)';
  } else {
    boxShadow = 'none';
  }

  let transform: string;
  if (isParentBox) {
    transform = 'none';
  } else if (isHovered || isActuallySelected) {
    transform = 'scale(1.02)';
  } else {
    transform = 'scale(1)';
  }

  let opacity: number;
  if (isParentBox) {
    opacity = 0;
  } else if (isHovered || isActuallySelected) {
    opacity = 1;
  } else {
    opacity = 0.9;
  }

  const boxElement = (
    <Box
      borderRadius="$1"
      style={{
        position: 'absolute',
        cursor: isParentBox ? 'default' : 'pointer', // Parent boxes are not clickable
        left: coords.left,
        top: coords.top,
        width: Math.max(coords.width, 8), // Minimum width for visibility
        height: Math.max(coords.height, 8), // Minimum height for visibility
        zIndex, // Parent boxes have lower z-index
        transition: isParentBox ? 'none' : 'all 0.2s ease-in-out', // No transitions for parent boxes
        background: getBackgroundColor(),
        border: '2px solid',
        borderColor: getBorderColor(),
        boxShadow,
        transform,
        opacity, // Parent boxes are invisible
        pointerEvents: isParentBox ? 'none' : 'auto', // Disable pointer events for parent boxes
      }}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onClick={handleBoxClick}
    />
  );

  // Only wrap with Tooltip if not a parent box (parent boxes don't need tooltips)
  // Parse boxes get tooltips with type information
  if (isParentBox) {
    return boxElement;
  }

  return (
    <Tooltip text={getTooltipText()} placement="top" maxWidth={300}>
      {boxElement}
    </Tooltip>
  );
};

// Helper function to check if one box is contained within another
const isBoxContained = (
  innerBox: { left: number; top: number; width: number; height: number },
  outerBox: { left: number; top: number; width: number; height: number },
  threshold: number = 5, // pixels tolerance
): boolean => {
  return (
    innerBox.left >= outerBox.left - threshold &&
    innerBox.top >= outerBox.top - threshold &&
    innerBox.left + innerBox.width <= outerBox.left + outerBox.width + threshold &&
    innerBox.top + innerBox.height <= outerBox.top + outerBox.height + threshold
  );
};

// Helper function to find field ID by numeric ID
const findFieldIdByNumericId = (numericId: number | null | undefined): string | null => {
  if (!numericId) {
    return null;
  }

  // Get the layoutFields from the store to find matching field
  const { layoutFields } = useDocumentIntelligenceStore.getState();

  // Find field with matching citationId
  const matchingField = layoutFields.find((field) => field.citationId === numericId);

  if (matchingField) {
    return matchingField.id;
  }
  return null;
};

// Advanced coordinate calculation for react-pdf
const calculateReactPdfCoordinates = (
  bbox: { left: number; top: number; width?: number; height?: number; page?: number },
  pageWidth: number,
  pageHeight: number,
  scale: number,
) => {
  try {
    const pdfLeft = bbox.left;
    const pdfTop = bbox.top;
    const pdfWidth = bbox.width || 0;
    const pdfHeight = bbox.height || 0;

    // Determine if coordinates are normalized (0-1) or in PDF points
    const isNormalized = pdfLeft <= 1 && pdfTop <= 1 && pdfWidth <= 1 && pdfHeight <= 1;

    let screenLeft: number;
    let screenTop: number;
    let screenWidth: number;
    let screenHeight: number;

    if (isNormalized) {
      // Coordinates are normalized (0-1 range) - scale to page dimensions
      screenLeft = pdfLeft * pageWidth;
      screenTop = pdfTop * pageHeight;
      screenWidth = pdfWidth * pageWidth;
      screenHeight = pdfHeight * pageHeight;
    } else {
      // Coordinates are in PDF points - need to handle coordinate system conversion
      screenLeft = pdfLeft * scale;
      screenWidth = pdfWidth * scale;
      screenHeight = pdfHeight * scale;

      // Handle coordinate system conversion: PDF uses bottom-left origin, screen uses top-left
      // Convert from PDF coordinates to screen coordinates
      const pdfPageHeight = pageHeight / scale; // Get original PDF page height
      screenTop = (pdfPageHeight - pdfTop - pdfHeight) * scale;

      // If the calculated position seems wrong, try alternative conversion
      if (screenTop < 0 || screenTop > pageHeight) {
        screenTop = pdfTop * scale;
      }
    }

    // Minimal padding for precise highlighting (like Reducto)
    const paddingX = 1; // Minimal padding
    const paddingY = 1; // Minimal padding

    const result = {
      left: screenLeft - paddingX,
      top: screenTop - paddingY,
      width: screenWidth + paddingX * 2,
      height: screenHeight + paddingY * 2,
    };

    return result;
  } catch (error) {
    // Silently handle coordinate calculation errors
    return null;
  }
};

// PDF Annotation Overlay Component
interface AnnotationOverlayProps {
  pageNumber: number;
  pageWidth: number;
  pageHeight: number;
  scale: number;
  extractedData: Record<string, unknown> | null; // Add extractedData for citations
  parseData: Record<string, unknown> | null; // Add parseData for parse bounding boxes
  selectedFieldId: string | null;
  setSelectedFieldId: (fieldId: string | null) => void;
}

const AnnotationOverlay: FC<AnnotationOverlayProps> = ({
  pageNumber,
  pageWidth,
  pageHeight,
  scale,
  extractedData,
  parseData,
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
      numericId?: number | null; // Add numeric ID for matching with layoutFields
      type?: string; // Add type information for parse boxes
      confidence?: string; // Add confidence information for parse boxes
    }>
  >([]);

  // Get showingParseBoxes state from store
  const { showingParseBoxes } = useDocumentIntelligenceStore();

  // Handle citation box click to select corresponding field in right panel
  const handleCitationClick = (fieldId: string, fieldName: string, numericId?: number | null) => {
    // First try to find the corresponding field row by numeric ID
    const matchingFieldId = findFieldIdByNumericId(numericId);

    if (matchingFieldId) {
      // Toggle selection
      const newSelectedId = selectedFieldId === matchingFieldId ? null : matchingFieldId;
      setSelectedFieldId(newSelectedId);

      // Scroll to the corresponding field in the right panel
      if (newSelectedId) {
        scrollToField(newSelectedId);
      }
    } else {
      // If no field match found by numeric ID, try to find by content
      const citationData = citationCoords.find((c) => c.fieldId === fieldId);
      const citationContent = citationData?.fieldValue || fieldName;

      const matchingFieldIdByContent = findFieldIdByContent(citationContent);

      if (matchingFieldIdByContent) {
        // Toggle selection
        const newSelectedId = selectedFieldId === matchingFieldIdByContent ? null : matchingFieldIdByContent;
        setSelectedFieldId(newSelectedId);

        // Scroll to the corresponding field in the right panel
        if (newSelectedId) {
          scrollToField(newSelectedId);
        }
      } else {
        // If no field match found, try to match with table rows
        const matchingTableRowId = findTableRowIdByContent(citationContent);

        if (matchingTableRowId) {
          // Toggle selection
          const newSelectedId = selectedFieldId === matchingTableRowId ? null : matchingTableRowId;
          setSelectedFieldId(newSelectedId);

          // Scroll to the corresponding table row in the right panel
          if (newSelectedId) {
            scrollToField(newSelectedId);
          }
        }
      }
    }
  };

  // Calculate citation coordinates from extractedData.citations or parseData
  useEffect(() => {
    const calculateCitationCoords = () => {
      const newCitationCoords: Array<{
        fieldId: string;
        coords: { left: number; top: number; width: number; height: number };
        fieldName: string;
        fieldValue: string;
        isMatched?: boolean; // Add flag to indicate if this citation matches a result
        numericId?: number | null; // Add numeric ID for matching with layoutFields
        isParentBox?: boolean; // Add flag to indicate if this is a parent box
        type?: string; // Add type information for parse boxes
        confidence?: string; // Add confidence information for parse boxes
      }> = [];

      // If showing parse boxes and we have parse data, use parse bounding boxes
      if (showingParseBoxes && parseData) {
        const parseBoundingBoxes = convertParseResultToBoundingBoxes(parseData as ParseDocumentResponsePayload);

        parseBoundingBoxes.forEach((bbox) => {
          // Convert parse bbox coordinates to screen coordinates
          const screenCoords = calculateReactPdfCoordinates(
            bbox.coords,
            pageWidth,
            pageHeight,
            scale,
          );

          if (screenCoords) {
            newCitationCoords.push({
              fieldId: bbox.fieldId,
              coords: screenCoords,
              fieldName: bbox.fieldName,
              fieldValue: bbox.fieldValue,
              isMatched: false, // Parse boxes don't have extracted values yet
              numericId: bbox.numericId,
              isParentBox: false, // Parse boxes are never parent boxes
              type: bbox.type, // Pass type information for tooltips
              confidence: bbox.confidence, // Pass confidence information for styling
            });
          }
        });
      } else if (extractedData?.citations) {
        // Get layoutFields to match citations with their citationIds
        const { layoutFields } = useDocumentIntelligenceStore.getState();

        // Track which citationIds have been used to prevent duplicates
        const usedCitationIds = new Set<number>();
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
            // Extract field name from path using same logic as schema rendering
            // This ensures nested fields like a.invoice_number and b.invoice_number get unique names
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
            // Use advanced coordinate calculation
            const screenCoords = calculateReactPdfCoordinates(bbox, pageWidth, pageHeight, scale);

            if (screenCoords) {
              // Find matching layoutField by content value
              let matchingNumericId: number | null = null;
              let isMatched = false;

              // Try exact match first (most precise)
              const exactMatch = layoutFields.find(
                (field) => field.value === content && !usedCitationIds.has(field.citationId || 0),
              );
              if (exactMatch) {
                matchingNumericId = exactMatch.citationId || null;
                isMatched = true;
                usedCitationIds.add(exactMatch.citationId || 0);
              } else {
                // Try partial matches, but prefer shorter matches (more specific)
                const partialMatches = layoutFields.filter(
                  (field) =>
                    field.value &&
                    (content.includes(field.value) || field.value.includes(content)) &&
                    !usedCitationIds.has(field.citationId || 0),
                );

                if (partialMatches.length > 0) {
                  // Sort by field value length (shorter = more specific) and take the best match
                  const bestMatch = partialMatches.sort((a, b) => (a.value?.length || 0) - (b.value?.length || 0))[0];
                  matchingNumericId = bestMatch.citationId || null;
                  isMatched = true;
                  usedCitationIds.add(bestMatch.citationId || 0);
                }
              }

              // Create a unique fieldId for this citation
              const fieldId = `citation-${pageNumber}-${index}`;

              newCitationCoords.push({
                fieldId,
                coords: screenCoords,
                fieldName,
                fieldValue: content,
                isMatched,
                numericId: matchingNumericId, // Add numeric ID for matching
                confidence: (citation as { confidence?: string }).confidence || 'high', // Extract confidence from citation, default to 'high'
              });
            }
          }
        });
      } else {
        // No citations found
      }

      // Deduplicate citations with identical bbox values - only keep the first occurrence
      const uniqueCitations = newCitationCoords.filter((citation, index) => {
        // Check if this citation has the same bbox as any previous citation
        const previousCitations = newCitationCoords.slice(0, index);
        const isDuplicate = previousCitations.some(
          (otherCitation) =>
            citation.coords.left === otherCitation.coords.left &&
            citation.coords.top === otherCitation.coords.top &&
            citation.coords.width === otherCitation.coords.width &&
            citation.coords.height === otherCitation.coords.height,
        );
        return !isDuplicate; // Keep this citation if it's not a duplicate
      });

      // Detect overlapping citation boxes and determine parent/child relationships
      const processedCitations = uniqueCitations.map((citation, index) => {
        // Check if this citation contains other citations
        const otherCitations = uniqueCitations.filter((_, i) => i !== index);
        const isParentBox = otherCitations.some((otherCitation) => {
          const thisBox = citation.coords;
          const otherBox = otherCitation.coords;
          // Check if this box contains the other box (this is parent)
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
      {/* Child bounding boxes (from citations) - interactive */}
      <Box style={{ transition: 'opacity 0.3s ease-in-out' }}>
        {citationCoords.map(({ fieldId, coords, fieldName, fieldValue, isMatched, isParentBox, numericId, type, confidence }) => (
          <Box key={`citation-overlay-${fieldId}`} style={{ pointerEvents: 'auto' }}>
            <CitationBox
              coords={coords}
              fieldName={fieldName}
              fieldValue={fieldValue}
              fieldId={fieldId}
              selectedFieldId={selectedFieldId}
              onBoxClick={(id) => handleCitationClick(id, fieldName, numericId)}
              onHoverChange={() => {}}
              isMatched={isMatched}
              isParentBox={isParentBox}
              numericId={numericId}
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

export const DocumentViewer: FC<DocumentViewerProps> = () => {
  // Get state from minimal Zustand store
  const { fileRef, extractedData, parseData, selectedFieldId, setSelectedFieldId, showingParseBoxes, setShowingParseBoxes } = useDocumentIntelligenceStore();

  // PDF state
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [numPages, setNumPages] = useState<number>(0);
  const [scale, setScale] = useState<number>(1.5); // Default 150% zoom
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [pdfBlob, setPdfBlob] = useState<Blob | null>(null);

  // PDF dimensions for overlay positioning
  const [pageWidth, setPageWidth] = useState<number>(0);
  const [pageHeight, setPageHeight] = useState<number>(0);

  const zoomPercentage = Math.round(scale * 100);

  // Load PDF from fileRef
  const loadPdfFromFile = useCallback(async () => {
    if (!fileRef) {
      setError('No PDF file selected');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      // Create a blob from the File object
      const blob = new Blob([fileRef], { type: 'application/pdf' });
      setPdfBlob(blob);

      // For now, assume 1 page - in real implementation this comes from PDF parsing
      setNumPages(1);
      setCurrentPage(1);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to load PDF';
      setError(errorMsg);
    } finally {
      setIsLoading(false);
    }
  }, [fileRef]);

  // Load PDF when component mounts or fileRef changes
  useEffect(() => {
    if (fileRef) {
      loadPdfFromFile();
    }
  }, [fileRef, loadPdfFromFile]);

  // PDF document loading handlers
  const onDocumentLoadSuccess = (document: PDFDocumentProxy) => {
    setNumPages(document.numPages);
    setCurrentPage(1);
  };

  const onDocumentLoadError = (err: Error) => {
    setError(`Failed to load PDF: ${err.message}`);
  };

  // Page rendering handlers
  const onPageLoadSuccess = (page: PDFPageProxy) => {
    const viewport = page.getViewport({ scale: 1 });
    setPageWidth(viewport.width * scale);
    setPageHeight(viewport.height * scale);
  };

  // Navigation handlers
  const goToPage = (pageNumber: number) => {
    if (pageNumber >= 1 && pageNumber <= numPages) {
      setCurrentPage(pageNumber);
    }
  };

  const changeScale = (newScale: number) => {
    const clampedScale = Math.max(0.5, Math.min(3.0, newScale));
    setScale(clampedScale);
  };

  if (isLoading) {
    return (
      <Box display="flex" alignItems="center" justifyContent="center" height="100%">
        <Typography>Loading PDF...</Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Box display="flex" alignItems="center" justifyContent="center" height="100%" flexDirection="column" gap="$16">
        <Typography color="content.error">{error}</Typography>
        <Button onClick={loadPdfFromFile} variant="outline">
          Retry Loading PDF
        </Button>
      </Box>
    );
  }

  if (!fileRef || !pdfBlob) {
    return (
      <Box display="flex" alignItems="center" justifyContent="center" height="100%" flexDirection="column" gap="$16">
        <Typography>No PDF file selected</Typography>
        <Button onClick={loadPdfFromFile} variant="outline">
          Load PDF
        </Button>
      </Box>
    );
  }

  return (
    <Box
      borderRadius="$8"
      display="flex"
      flexDirection="column"
      style={{ height: '100%', position: 'relative' }}
      borderWidth="1px"
      borderColor="border.subtle"
      flex="1"
      minHeight="0"
      minWidth="0"
    >
      {/* PDF Content Area */}
      <Box
        backgroundColor="background.primary"
        borderRadius="$8"
        display="flex"
        flexDirection="column"
        className="relative h-full"
        flex="1"
        minHeight="0"
      >
        <Box
          flex="1"
          style={{
            padding: '8px',
            scrollBehavior: 'smooth',
            position: 'relative',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'flex-start',
            minHeight: '0',
            overflow: 'auto',
            maxWidth: '100%',
            maxHeight: '100%',
          }}
        >
          <Box style={{ position: 'relative', maxWidth: '100%', maxHeight: '100%' }}>
            {/* React-PDF Document and Page */}
            <Box style={{ maxWidth: '100%', maxHeight: '100%' }}>
              <Document
                file={pdfBlob}
                onLoadSuccess={onDocumentLoadSuccess}
                onLoadError={onDocumentLoadError}
                loading={<Typography>Loading PDF...</Typography>}
                error={<Typography color="content.error">Failed to load PDF</Typography>}
                noData={<Typography>No PDF data</Typography>}
                className="react-pdf__Document"
              >
                <Page
                  pageNumber={currentPage}
                  scale={scale}
                  onLoadSuccess={onPageLoadSuccess}
                  loading={<Typography>Loading page...</Typography>}
                  error={<Typography color="content.error">Failed to load page</Typography>}
                  noData={<Typography>No page data</Typography>}
                  className="react-pdf__Page"
                  canvasBackground="white"
                  renderTextLayer
                  renderAnnotationLayer
                />
              </Document>
            </Box>

            {/* Annotation Overlay - positioned absolutely over the PDF page */}
            {pageWidth > 0 && pageHeight > 0 && (
              <AnnotationOverlay
                pageNumber={currentPage}
                pageWidth={pageWidth}
                pageHeight={pageHeight}
                scale={scale}
                extractedData={extractedData}
                parseData={parseData}
                selectedFieldId={selectedFieldId}
                setSelectedFieldId={setSelectedFieldId}
              />
            )}
          </Box>
        </Box>

        {/* Page Number Display - Fixed at bottom of PDF viewer */}
        <Box
          textAlign="center"
          fontSize="$12"
          color="content.subtle"
          backgroundColor="background.primary"
          borderRadius="$4"
          boxShadow="0 1px 2px 0 rgba(0, 0, 0, 0.05)"
          style={{
            position: 'absolute',
            bottom: '4rem',
            left: '50%',
            transform: 'translateX(-50%)',
            zIndex: '10',
            padding: '3px 16px',
          }}
        >
          Page {currentPage} of {numPages}
        </Box>
      </Box>

      {/* Bottom Controls */}
      <Box
        padding="$8"
        backgroundColor="background.subtle"
        flexShrink="0"
        display="flex"
        alignItems="center"
        justifyContent="center"
      >
        <Box display="flex" alignItems="center" justifyContent="space-between" gap="$16">
          {/* Page Navigation */}
          <Box display="flex" alignItems="center">
            <Button disabled={currentPage <= 1} variant="ghost" round onClick={() => goToPage(currentPage - 1)}>
              <IconArrowLeft />
            </Button>
            <Typography fontSize="$16" fontWeight="medium" textAlign="center" style={{ minWidth: '80px' }}>
              {currentPage} / {numPages}
            </Typography>
            <Button disabled={currentPage >= numPages} variant="ghost" round onClick={() => goToPage(currentPage + 1)}>
              <IconArrowRight />
            </Button>
          </Box>

          <Divider orientation="vertical" />

          {/* Parse/Extract Toggle - only show when both parse and extract data exist */}
          {parseData && extractedData && (
            <>
              <Box display="flex" alignItems="center" gap="$8" style={{ transition: 'opacity 0.3s ease-in-out' }}>
                <Typography fontSize="$14">
                  Parse
                </Typography>
                <Switch
                  checked={!showingParseBoxes}
                  onChange={(e) => setShowingParseBoxes(!e.target.checked)}
                  aria-labelledby="parse-extract-toggle"
                />
                <Typography fontSize="$14">
                  Extract
                </Typography>
              </Box>
              <Divider orientation="vertical" />
            </>
          )}

          {/* Scale Controls */}
          <Box display="flex" alignItems="center">
            <Button disabled={scale <= 0.5} variant="ghost" round onClick={() => changeScale(scale - 0.25)}>
              <IconMinus />
            </Button>
            <Typography fontSize="$16" fontWeight="medium" textAlign="center" style={{ minWidth: '70px' }}>
              {zoomPercentage}%
            </Typography>
            <Button disabled={scale >= 3.0} variant="ghost" round onClick={() => changeScale(scale + 0.25)}>
              <IconPlus />
            </Button>
          </Box>
        </Box>
      </Box>
    </Box>
  );
};
