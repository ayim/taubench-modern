import { Box, Button, Tooltip, Typography } from '@sema4ai/components';
import { FC, useState, useEffect, useRef } from 'react';
import { CitationBox } from './CitationBox';
import { formatFieldName, isBoxContained, calculateReactPdfCoordinates } from '../utils';

type CommentAnchor = { x: number; y: number; normalized?: boolean };

const extractChunksFromParseData = (parseData: Record<string, unknown> | null): Array<Record<string, unknown>> => {
  if (!parseData || typeof parseData !== 'object') return [];
  const source =
    'result' in parseData && parseData.result && typeof parseData.result === 'object'
      ? (parseData.result as Record<string, unknown>)
      : parseData;
  const chunks = source?.chunks;
  return Array.isArray(chunks) ? (chunks as Array<Record<string, unknown>>) : [];
};

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
  const chunks = extractChunksFromParseData(parseData);

  chunks.forEach((chunk, index) => {
    const chunkPageFromPage = chunk.page as number | undefined;
    const chunkPageFromBbox = (chunk.bbox as { page?: number; original_page?: number } | undefined)?.page;
    const chunkOriginalPage =
      (chunk as { original_page?: number }).original_page ??
      (chunk.bbox as { original_page?: number } | undefined)?.original_page;
    let chunkPage = pageNumber;
    if (typeof chunkPageFromPage === 'number') {
      chunkPage = chunkPageFromPage;
    } else if (typeof chunkPageFromBbox === 'number') {
      chunkPage = chunkPageFromBbox;
    } else if (typeof chunkOriginalPage === 'number') {
      chunkPage = chunkOriginalPage;
    }
    const type = chunk.type as string | undefined;
    const confidence = chunk.confidence as string | undefined;
    const content = chunk.content as string | undefined;

    // Prefer block-level bboxes if present
    const blocks = (chunk.blocks as Array<Record<string, unknown>>) || [];
    if (blocks.length > 0) {
      blocks.forEach((block, blockIdx) => {
        const blockBbox = block.bbox as
          | { left: number; top: number; width?: number; height?: number; page?: number; original_page?: number }
          | undefined;
        const blockOriginalPage = (blockBbox?.original_page as number | undefined) ?? chunkOriginalPage;
        const blockPageRaw = (blockBbox?.page as number | undefined) ?? chunkPage;
        let blockPage = chunkPage;
        if (typeof blockPageRaw === 'number') {
          blockPage = blockPageRaw;
        } else if (typeof blockOriginalPage === 'number') {
          blockPage = blockOriginalPage;
        }
        if (
          (blockPage === pageNumber || blockOriginalPage === pageNumber) &&
          blockBbox &&
          blockBbox.width !== undefined &&
          blockBbox.height !== undefined
        ) {
          bboxes.push({
            fieldId: `parse-${pageNumber}-${index}-${blockIdx}`,
            coords: {
              left: blockBbox.left,
              top: blockBbox.top,
              width: blockBbox.width,
              height: blockBbox.height,
              page: blockBbox.page ?? blockBbox.original_page ?? blockPage,
            },
            fieldName: (block.type as string | undefined) || type || 'text',
            fieldValue: (block.content as string | undefined) || content || '',
            numericId: null,
            type: (block.type as string | undefined) || type,
            confidence: (block.confidence as string | undefined) || confidence,
          });
        }
      });
      return;
    }

    // Fallback to chunk bbox if no blocks
    const bbox = chunk.bbox as
      | { left: number; top: number; width?: number; height?: number; page?: number; original_page?: number }
      | undefined;
    if (
      (chunkPage === pageNumber || chunkOriginalPage === pageNumber || bbox?.original_page === pageNumber) &&
      bbox &&
      bbox.width !== undefined &&
      bbox.height !== undefined
    ) {
      bboxes.push({
        fieldId: `parse-${chunkPage}-${index}`,
        coords: {
          left: bbox.left,
          top: bbox.top,
          width: bbox.width,
          height: bbox.height,
          page: bbox.page ?? bbox.original_page ?? chunkPage,
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
  comments?: Record<string, { text: string; anchor?: CommentAnchor }>;
  onSaveComment?: (fieldId: string, text: string, anchor: CommentAnchor) => void;
  onDeleteComment?: (fieldId: string) => void;
  commentsDisabled?: boolean;
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
  comments,
  onSaveComment,
  onDeleteComment,
  commentsDisabled = false,
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
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [commentAnchors, setCommentAnchors] = useState<Record<number, Record<string, CommentAnchor>>>({});
  const [contextMenu, setContextMenu] = useState<{
    fieldId: string;
    x: number;
    y: number;
  } | null>(null);
  const [draftComment, setDraftComment] = useState<string>('');

  // Normalize any legacy pixel anchors into page-relative coordinates once per render cycle
  useEffect(() => {
    if (!comments || pageWidth === 0 || pageHeight === 0) return;
    const existingAnchors = commentAnchors[pageNumber] || {};
    const converted: Record<string, CommentAnchor> = {};

    Object.entries(comments).forEach(([fieldId, comment]) => {
      const { anchor } = comment;
      if (!anchor || anchor.normalized || (anchor.x <= 1 && anchor.y <= 1)) return;
      if (existingAnchors[fieldId]?.normalized) return;
      converted[fieldId] = { x: anchor.x / pageWidth, y: anchor.y / pageHeight, normalized: true };
    });

    if (Object.keys(converted).length > 0) {
      setCommentAnchors((prev) => ({
        ...prev,
        [pageNumber]: { ...(prev[pageNumber] ?? {}), ...converted },
      }));
    }
  }, [comments, pageNumber, pageWidth, pageHeight, commentAnchors]);

  // Handle citation box click
  const handleCitationClick = (fieldId: string) => {
    // Toggle selection
    const newSelectedId = selectedFieldId === fieldId ? null : fieldId;
    setSelectedFieldId(newSelectedId);
  };

  const handleContextMenuOpen = (event: React.MouseEvent, fieldId: string) => {
    if (commentsDisabled) return;
    event.stopPropagation();
    if (!containerRef.current) return;
    const existing = comments?.[fieldId]?.text ?? '';
    setDraftComment(existing);
    const rect = containerRef.current.getBoundingClientRect();
    const relativeX = event.clientX - rect.left;
    const relativeY = event.clientY - rect.top;
    const menuWidth = 280;
    const padding = 12;
    const clampedX = Math.min(Math.max(padding, relativeX), pageWidth - menuWidth - padding);
    const clampedY = Math.min(Math.max(padding, relativeY + 8), pageHeight - 220);
    setContextMenu({ fieldId, x: clampedX, y: clampedY });
  };

  const handleSave = () => {
    if (contextMenu && !commentsDisabled) {
      const trimmed = draftComment.trim();
      const anchor: CommentAnchor =
        pageWidth > 0 && pageHeight > 0
          ? { x: contextMenu.x / pageWidth, y: contextMenu.y / pageHeight, normalized: true }
          : { x: contextMenu.x, y: contextMenu.y };
      onSaveComment?.(contextMenu.fieldId, trimmed, anchor);
      if (trimmed) {
        setCommentAnchors((prev) => ({
          ...prev,
          [pageNumber]: { ...(prev[pageNumber] ?? {}), [contextMenu.fieldId]: anchor },
        }));
      } else {
        setCommentAnchors((prev) => {
          const next = { ...prev };
          const current = { ...(next[pageNumber] ?? {}) };
          delete current[contextMenu.fieldId];
          next[pageNumber] = current;
          return next;
        });
      }
      setContextMenu(null);
    }
  };

  const handleDelete = () => {
    if (contextMenu && !commentsDisabled) {
      onDeleteComment?.(contextMenu.fieldId);
      setCommentAnchors((prev) => {
        const next = { ...prev };
        const current = { ...(next[pageNumber] ?? {}) };
        delete current[contextMenu.fieldId];
        next[pageNumber] = current;
        return next;
      });
      setContextMenu(null);
    }
  };

  const handleOverlayClick = () => {
    if (contextMenu) {
      setContextMenu(null);
    }
  };

  const getAnchorPoint = (anchor?: CommentAnchor | null) => {
    if (!anchor) return null;
    const shouldTreatAsNormalized = anchor.normalized || (anchor.x <= 1 && anchor.y <= 1);
    if (shouldTreatAsNormalized && pageWidth > 0 && pageHeight > 0) {
      return { x: anchor.x * pageWidth, y: anchor.y * pageHeight };
    }
    return { x: anchor.x, y: anchor.y };
  };

  const handleCommentBadgeClick = (fieldId: string) => {
    if (!containerRef.current) return;
    const existing = comments?.[fieldId]?.text ?? '';
    setDraftComment(existing);
    const anchor = (commentAnchors[pageNumber] || {})[fieldId] || comments?.[fieldId]?.anchor;
    const anchorPoint = getAnchorPoint(anchor);
    const fallbackX = Math.max(12, Math.min(pageWidth - 280 - 12, pageWidth / 2 - 140));
    const fallbackY = Math.max(12, Math.min(pageHeight - 220, pageHeight / 2 - 60));
    setContextMenu({
      fieldId,
      x: anchorPoint?.x ?? fallbackX,
      y: anchorPoint?.y ?? fallbackY,
    });
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
      ref={containerRef}
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
      onClick={handleOverlayClick}
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
              onContextMenu={handleContextMenuOpen}
              onHoverChange={() => {}}
              isMatched={isMatched}
              isParentBox={isParentBox}
              isParseBox={showingParseBoxes}
              type={type}
              confidence={confidence}
              hasComment={Boolean(comments?.[fieldId])}
            />
          </Box>
        ))}
      </Box>
      {comments &&
        Object.entries(comments).map(([fieldId, text]) => {
          const anchor = (commentAnchors[pageNumber] || {})[fieldId] || text.anchor;
          const anchorPoint = getAnchorPoint(anchor);
          if (!anchorPoint) return null;
          return (
            <Tooltip key={`comment-anchor-${fieldId}`} text={text.text} placement="top" maxWidth={240}>
              <Box
                style={{
                  position: 'absolute',
                  left: anchorPoint.x - 6,
                  top: anchorPoint.y - 6,
                  width: 12,
                  height: 12,
                  background: 'rgb(59,130,246)',
                  borderRadius: '50%',
                  border: '2px solid white',
                  boxShadow: '0 2px 6px rgba(0,0,0,0.2)',
                  cursor: 'pointer',
                  pointerEvents: 'auto',
                  zIndex: 3500,
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  handleCommentBadgeClick(fieldId);
                }}
              />
            </Tooltip>
          );
        })}
      {contextMenu && (
        <Box
          style={{
            position: 'absolute',
            top: contextMenu.y,
            left: contextMenu.x,
            zIndex: 4000,
            minWidth: 220,
            maxWidth: 280,
            background: 'white',
            border: '1px solid var(--rc-color-border-subtle, #e5e7eb)',
            borderRadius: 8,
            boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
            padding: 12,
            pointerEvents: 'auto',
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <Typography fontSize="$12" fontWeight="bold" marginBottom="$4">
            Comment
          </Typography>
          <textarea
            value={draftComment}
            onChange={(e) => setDraftComment(e.target.value)}
            style={{
              width: '100%',
              minHeight: 80,
              resize: 'vertical',
              padding: 8,
              borderRadius: 6,
              border: '1px solid var(--rc-color-border-subtle, #e5e7eb)',
              fontSize: 12,
            }}
          />
          <Box display="flex" justifyContent="flex-end" gap="$2" marginTop="$4">
            {comments?.[contextMenu.fieldId] && (
              <Button size="small" variant="ghost" onClick={handleDelete} disabled={commentsDisabled}>
                Delete
              </Button>
            )}
            <Button size="small" variant="ghost" onClick={() => setContextMenu(null)}>
              Cancel
            </Button>
            <Button
              size="small"
              variant="primary"
              onClick={handleSave}
              disabled={!draftComment.trim() || commentsDisabled}
            >
              Save
            </Button>
          </Box>
        </Box>
      )}
    </Box>
  );
};

export default AnnotationOverlay;
