import { useState, useCallback, useRef, useEffect } from 'react';

interface UseResultsSelectionProps {
  blocks: Array<{ id: string; page?: number }>;
}

interface UseResultsSelectionReturn {
  selectedBlockId: string | null;
  selectedFieldId: string | null;
  handlePdfFieldClick: (fieldId: string) => void;
  handleBlockClick: (blockId: string) => void;
  registerBlockRef: (blockId: string, element: HTMLElement | null) => void;
  clearSelection: () => void;
}

/**
 * Hook to manage bidirectional selection between PDF annotations and result blocks
 *
 * Handles:
 * - Clicking a PDF bounding box → select and scroll to corresponding result block
 * - Clicking a result block → select corresponding PDF annotation
 * - Smooth scrolling between panels
 */
export const useResultsSelection = ({ blocks }: UseResultsSelectionProps): UseResultsSelectionReturn => {
  const [selectedBlockId, setSelectedBlockId] = useState<string | null>(null);
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(null);
  const blockRefs = useRef<Map<string, HTMLElement>>(new Map());

  /**
   * Map PDF field ID to block ID
   * Field ID format: "parse-{chunkIndex}-{blockIndex}" or "citation-{path}-{index}"
   * Block ID format: "block-{chunkIndex}-{blockIndex}" or "extract-{path}"
   */
  const fieldIdToBlockId = useCallback(
    (fieldId: string): string | null => {
      // Handle parse field IDs: "parse-{chunkIndex}-{blockIndex}"
      const parseMatch = fieldId.match(/parse-(\d+)-(\d+)/);
      if (parseMatch) {
        const [, chunkIndex, blockIndex] = parseMatch;
        const blockId = `block-${chunkIndex}-${blockIndex}`;
        return blocks.find((b) => b.id === blockId) ? blockId : null;
      }

      // Handle citation field IDs: "citation-{path}-{index}"
      const citationMatch = fieldId.match(/^citation-(.+)-\d+$/);
      if (citationMatch) {
        const [, path] = citationMatch;
        const blockId = `extract-${path}`;
        return blocks.find((b) => b.id === blockId) ? blockId : null;
      }

      return null;
    },
    [blocks],
  );

  /**
   * Map block ID to PDF field ID
   * Block ID format: "block-{chunkIndex}-{blockIndex}" or "extract-{path}"
   * Field ID format: "parse-{chunkIndex}-{blockIndex}" or "citation-{path}-{index}"
   */
  const blockIdToFieldId = useCallback((blockId: string): string | null => {
    // Handle parse blocks: "block-{chunkIndex}-{blockIndex}"
    const parseMatch = blockId.match(/block-(\d+)-(\d+)/);
    if (parseMatch) {
      const [, chunkIndex, blockIndex] = parseMatch;
      return `parse-${chunkIndex}-${blockIndex}`;
    }

    // Handle extract blocks: "extract-{path}"
    const extractMatch = blockId.match(/^extract-(.+)$/);
    if (extractMatch) {
      const [, path] = extractMatch;
      // Return a pattern that can match any citation with this path
      // The actual citation ID will be citation-{path}-{index}, we return the first one (index 0)
      return `citation-${path}-0`;
    }

    return null;
  }, []);

  /**
   * Handle PDF annotation click - select and scroll to result block
   */
  const handlePdfFieldClick = useCallback(
    (fieldId: string) => {
      const blockId = fieldIdToBlockId(fieldId);
      if (blockId) {
        setSelectedBlockId(blockId);
        setSelectedFieldId(fieldId);

        // Scroll block into view with smooth animation
        const element = blockRefs.current.get(blockId);
        if (element) {
          element.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }
    },
    [fieldIdToBlockId],
  );

  /**
   * Handle result block click - select corresponding PDF annotation
   */
  const handleBlockClick = useCallback(
    (blockId: string) => {
      setSelectedBlockId(blockId);

      // Find corresponding PDF field ID
      const fieldId = blockIdToFieldId(blockId);
      if (fieldId) {
        setSelectedFieldId(fieldId);
      }
    },
    [blockIdToFieldId],
  );

  /**
   * Register block element for scroll-into-view functionality
   */
  const registerBlockRef = useCallback((blockId: string, element: HTMLElement | null) => {
    if (element) {
      blockRefs.current.set(blockId, element);
    } else {
      blockRefs.current.delete(blockId);
    }
  }, []);

  /**
   * Clear current selection
   */
  const clearSelection = useCallback(() => {
    setSelectedBlockId(null);
    setSelectedFieldId(null);
  }, []);

  // Clean up refs when blocks change
  useEffect(() => {
    const currentRefs = blockRefs.current;
    const blockIds = new Set(blocks.map((b) => b.id));

    // Remove refs for blocks that no longer exist
    Array.from(currentRefs.keys()).forEach((id) => {
      if (!blockIds.has(id)) {
        currentRefs.delete(id);
      }
    });
  }, [blocks]);

  return {
    selectedBlockId,
    selectedFieldId,
    handlePdfFieldClick,
    handleBlockClick,
    registerBlockRef,
    clearSelection,
  };
};
