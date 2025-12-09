import { useState, useEffect, useCallback, useRef, RefObject } from 'react';

interface UseAnnotationDrawingProps {
  isAnnotating: boolean;
  pageWidth: number;
  pageHeight: number;
  currentPage: number;
  onAnnotationCreate?: (selection: {
    pageNumber: number;
    left: number;
    top: number;
    width: number;
    height: number;
    selectedText: string;
  }) => void;
  parseData: Record<string, unknown> | null;
  extractedData: Record<string, unknown> | null;
}

export const useAnnotationDrawing = ({
  isAnnotating,
  pageWidth,
  pageHeight,
  currentPage,
  onAnnotationCreate,
  parseData,
  extractedData,
}: UseAnnotationDrawingProps) => {
  const [isDrawing, setIsDrawing] = useState(false);
  const [drawStart, setDrawStart] = useState<{ x: number; y: number } | null>(null);
  const [drawEnd, setDrawEnd] = useState<{ x: number; y: number } | null>(null);
  const [annotationPopupPosition, setAnnotationPopupPosition] = useState<{ x: number; y: number } | null>(null);
  const [completedSelectionBounds, setCompletedSelectionBounds] = useState<{
    left: number;
    top: number;
    width: number;
    height: number;
  } | null>(null);
  const pageContainerRef = useRef<HTMLDivElement>(null);

  // Clear annotation popup and selection when exiting annotation mode
  useEffect(() => {
    if (!isAnnotating) {
      setAnnotationPopupPosition(null);
      setCompletedSelectionBounds(null);
      setIsDrawing(false);
      setDrawStart(null);
      setDrawEnd(null);
    }
  }, [isAnnotating]);

  // Text extraction helper function
  const extractTextFromSelection = useCallback(
    (
      left: number,
      top: number,
      width: number,
      height: number,
      normalizedLeft: number,
      normalizedTop: number,
      normalizedWidth: number,
      normalizedHeight: number,
    ): string => {
      let selectedText = '';

      // First, try to get text from browser's native selection (if user selected text by highlighting)
      const selection = window.getSelection();

      if (selection && selection.toString().trim()) {
        selectedText = selection.toString().trim();
      } else {
        // Fallback 2: Try to find text from existing extraction/parse data in the selected region
        const dataToSearch = parseData || extractedData;
        if (dataToSearch) {
          const textsInRegion: string[] = [];

          // Look through parse data chunks
          if (parseData && 'chunks' in parseData) {
            const chunks = (parseData.chunks as Array<Record<string, unknown>>) || [];
            chunks.forEach((chunk) => {
              const bbox = chunk.bbox as
                | { left: number; top: number; width: number; height: number; page?: number }
                | undefined;
              const page = chunk.page as number | undefined;
              const content = chunk.content as string | undefined;

              if (bbox && page === currentPage && content) {
                // Check if this chunk overlaps with our selection
                const chunkLeft = bbox.left <= 1 ? bbox.left : bbox.left / pageWidth;
                const chunkTop = bbox.top <= 1 ? bbox.top : bbox.top / pageHeight;
                const chunkRight = chunkLeft + (bbox.width <= 1 ? bbox.width : bbox.width / pageWidth);
                const chunkBottom = chunkTop + (bbox.height <= 1 ? bbox.height : bbox.height / pageHeight);

                const selRight = normalizedLeft + normalizedWidth;
                const selBottom = normalizedTop + normalizedHeight;

                // Check overlap
                const overlapsX = chunkLeft < selRight && chunkRight > normalizedLeft;
                const overlapsY = chunkTop < selBottom && chunkBottom > normalizedTop;

                if (overlapsX && overlapsY) {
                  textsInRegion.push(content);
                }
              }
            });
          }

          // Also check extractedData citations
          if (extractedData && 'citations' in extractedData && textsInRegion.length === 0) {
            // Helper to recursively find citations with bbox
            const findCitations = (
              obj: unknown,
              path: string = '',
            ): Array<{ content: string; bbox: unknown; page?: number }> => {
              const results: Array<{ content: string; bbox: unknown; page?: number }> = [];
              if (!obj || typeof obj !== 'object') return results;

              // Check if this is a citation object
              if ('bbox' in obj && 'content' in obj) {
                const citation = obj as Record<string, unknown>;
                results.push({
                  content: citation.content as string,
                  bbox: citation.bbox,
                  page:
                    citation.bbox && typeof citation.bbox === 'object' && 'page' in citation.bbox
                      ? ((citation.bbox as Record<string, unknown>).page as number)
                      : undefined,
                });
              }

              // Recurse through object properties
              Object.entries(obj).forEach(([key, value]) => {
                if (Array.isArray(value)) {
                  value.forEach((item, idx) => {
                    results.push(...findCitations(item, `${path}.${key}[${idx}]`));
                  });
                } else if (typeof value === 'object' && value !== null) {
                  results.push(...findCitations(value, `${path}.${key}`));
                }
              });

              return results;
            };

            const citations = findCitations((extractedData as Record<string, unknown>).citations);

            citations.forEach((citation) => {
              if (citation.bbox && citation.page === currentPage && citation.content) {
                const bbox = citation.bbox as { left: number; top: number; width: number; height: number };
                const chunkLeft = bbox.left <= 1 ? bbox.left : bbox.left / pageWidth;
                const chunkTop = bbox.top <= 1 ? bbox.top : bbox.top / pageHeight;
                const chunkRight = chunkLeft + (bbox.width <= 1 ? bbox.width : bbox.width / pageWidth);
                const chunkBottom = chunkTop + (bbox.height <= 1 ? bbox.height : bbox.height / pageHeight);

                const selRight = normalizedLeft + normalizedWidth;
                const selBottom = normalizedTop + normalizedHeight;

                const overlapsX = chunkLeft < selRight && chunkRight > normalizedLeft;
                const overlapsY = chunkTop < selBottom && chunkBottom > normalizedTop;

                if (overlapsX && overlapsY) {
                  textsInRegion.push(citation.content);
                }
              }
            });
          }

          if (textsInRegion.length > 0) {
            selectedText = textsInRegion.join(' ').trim();
          }
        }

        // Fallback 3: Try to extract from PDF text layer
        if (!selectedText) {
          try {
            // Find the text layer within the page container
            const textLayer = pageContainerRef.current?.querySelector('.react-pdf__Page__textContent');

            if (textLayer) {
              // Get all text elements in the text layer
              // React-PDF renders text in span elements
              const textElements = Array.from(textLayer.querySelectorAll('span'));

              if (textElements.length === 0) {
                // Fallback: just grab the entire text content
                selectedText = textLayer.textContent?.trim() || '';
              } else {
                const selectedTexts: string[] = [];

                textElements.forEach((element) => {
                  const elemRect = element.getBoundingClientRect();
                  const pageRect = pageContainerRef.current!.getBoundingClientRect();

                  // Convert element position to page-relative coordinates
                  const elemLeft = elemRect.left - pageRect.left;
                  const elemTop = elemRect.top - pageRect.top;
                  const elemRight = elemLeft + elemRect.width;
                  const elemBottom = elemTop + elemRect.height;

                  // Check if element overlaps with selection
                  const overlapsX = elemLeft < left + width && elemRight > left;
                  const overlapsY = elemTop < top + height && elemBottom > top;

                  if (overlapsX && overlapsY) {
                    const text = element.textContent || '';
                    selectedTexts.push(text);
                  }
                });

                selectedText = selectedTexts.join(' ').trim();
              }
            }
          } catch (err) {
            // Silently fail if text extraction doesn't work
          }
        }
      }

      return selectedText;
    },
    [currentPage, pageWidth, pageHeight, parseData, extractedData],
  );

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (!isAnnotating) return;

      const rect = pageContainerRef.current?.getBoundingClientRect();
      if (!rect) return;

      setIsDrawing(true);
      setDrawStart({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      });
      setDrawEnd(null);
    },
    [isAnnotating],
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isDrawing || !drawStart) return;

      const rect = pageContainerRef.current?.getBoundingClientRect();
      if (!rect) return;

      setDrawEnd({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      });
    },
    [isDrawing, drawStart],
  );

  const handleMouseUp = useCallback(
    (e: React.MouseEvent) => {
      if (!isDrawing || !drawStart) {
        setIsDrawing(false);
        return;
      }

      // Calculate selection bounds
      const rect = pageContainerRef.current?.getBoundingClientRect();
      if (!rect) {
        setIsDrawing(false);
        setDrawStart(null);
        setDrawEnd(null);
        return;
      }

      // Use drawEnd if available, otherwise calculate from mouse position
      const endPos = drawEnd || {
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      };

      const left = Math.min(drawStart.x, endPos.x);
      const top = Math.min(drawStart.y, endPos.y);
      const width = Math.abs(endPos.x - drawStart.x);
      const height = Math.abs(endPos.y - drawStart.y);

      // Only create annotation if selection is meaningful (>10px)
      if (width > 10 && height > 10 && pageWidth > 0 && pageHeight > 0) {
        // Convert screen coordinates to normalized PDF coordinates (0-1 range)
        const normalizedLeft = left / pageWidth;
        const normalizedTop = top / pageHeight;
        const normalizedWidth = width / pageWidth;
        const normalizedHeight = height / pageHeight;

        // Extract text from selection
        const selectedText = extractTextFromSelection(
          left,
          top,
          width,
          height,
          normalizedLeft,
          normalizedTop,
          normalizedWidth,
          normalizedHeight,
        );

        onAnnotationCreate?.({
          pageNumber: currentPage,
          left: normalizedLeft,
          top: normalizedTop,
          width: normalizedWidth,
          height: normalizedHeight,
          selectedText,
        });

        // Position popup directly below the selection box, centered horizontally
        const viewportLeft = rect.left + left;
        const viewportRight = rect.left + left + width;
        const viewportBottom = rect.top + top + height;

        // Calculate center X and bottom Y in viewport space
        const viewportCenterX = (viewportLeft + viewportRight) / 2;
        const viewportBottomY = viewportBottom;

        // Store position for the annotation popup
        setAnnotationPopupPosition({
          x: viewportCenterX,
          y: viewportBottomY + 10,
        });

        // Store the completed selection bounds to keep the blue box visible
        setCompletedSelectionBounds({ left, top, width, height });
      }

      setIsDrawing(false);
      setDrawStart(null);
      setDrawEnd(null);
    },
    [isDrawing, drawStart, drawEnd, pageWidth, pageHeight, currentPage, onAnnotationCreate, extractTextFromSelection],
  );

  const handleMouseLeave = useCallback(() => {
    if (isDrawing) {
      setIsDrawing(false);
      setDrawStart(null);
      setDrawEnd(null);
    }
  }, [isDrawing]);

  return {
    isDrawing,
    drawStart,
    drawEnd,
    annotationPopupPosition,
    completedSelectionBounds,
    pageContainerRef: pageContainerRef as RefObject<HTMLDivElement>,
    handleMouseDown,
    handleMouseMove,
    handleMouseUp,
    handleMouseLeave,
    setAnnotationPopupPosition,
    setCompletedSelectionBounds,
  };
};
