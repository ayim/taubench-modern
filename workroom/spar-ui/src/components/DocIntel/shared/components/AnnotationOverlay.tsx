import { FC, useState, useEffect, useCallback } from 'react';
import { Box, Tooltip } from '@sema4ai/components';
import {
  BoundingBox,
  parseDataToBoundingBoxes,
  extractDataToBoundingBoxes,
  deduplicateBoundingBoxes,
  markParentBoxes,
} from '../utils/boundingBoxes';

interface AnnotationOverlayProps {
  pageNumber: number;
  pageWidth: number;
  pageHeight: number;
  scale: number;
  parseData: Record<string, unknown> | null;
  extractedData: Record<string, unknown> | null;
  showingParseBoxes: boolean;
  selectedFieldId: string | null;
  onFieldSelect?: (fieldId: string | null) => void;
}

// Bounding box visualization component
interface BoundingBoxComponentProps {
  box: BoundingBox;
  isParseBox: boolean;
  selectedFieldId: string | null;
  onBoxClick?: (fieldId: string) => void;
}

const BoundingBoxComponent: FC<BoundingBoxComponentProps> = ({ box, isParseBox, selectedFieldId, onBoxClick }) => {
  const [isHovered, setIsHovered] = useState(false);
  const isSelected = box.fieldId === selectedFieldId;

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (box.isParentBox || isParseBox) return; // Non-interactive
    if (onBoxClick) onBoxClick(box.fieldId);
  };

  const getBorderColor = () => {
    if (box.isParentBox) return 'transparent';

    if (isParseBox) {
      // Type-based colors for parse boxes
      switch (box.type?.toLowerCase()) {
        case 'title':
          return 'rgb(220, 38, 38)';
        case 'header':
          return 'rgb(234, 88, 12)';
        case 'footer':
          return 'rgb(107, 114, 128)';
        case 'table':
          return 'rgb(34, 197, 94)';
        case 'figure':
          return 'rgb(147, 51, 234)';
        case 'section header':
          return 'rgb(245, 158, 11)';
        case 'text':
        default:
          return 'rgb(22, 95, 140)';
      }
    }

    // Extract boxes use green
    return 'rgb(22, 140, 43)';
  };

  const getBackgroundColor = () => {
    if (box.isParentBox) return 'transparent';

    if (isHovered || isSelected) return 'transparent';

    if (isParseBox) {
      switch (box.type?.toLowerCase()) {
        case 'title':
          return 'rgb(220 38 38 / 20%)';
        case 'header':
          return 'rgb(234 88 12 / 20%)';
        case 'footer':
          return 'rgb(107 114 128 / 20%)';
        case 'table':
          return 'rgb(34 197 94 / 20%)';
        case 'figure':
          return 'rgb(147 51 234 / 20%)';
        case 'section header':
          return 'rgb(245 158 11 / 20%)';
        case 'text':
        default:
          return 'rgb(25 148 238 / 20%)';
      }
    }

    return 'rgb(39 214 60 / 20%)';
  };

  const getTooltipText = () => {
    if (isParseBox && box.type) {
      return (
        <span style={{ fontSize: '12px', lineHeight: '1.3' }}>
          Type: {box.type}
          {box.confidence && box.confidence !== 'high' && (
            <>
              <br />
              Confidence: {box.confidence}
            </>
          )}
        </span>
      );
    }

    return (
      <span style={{ fontSize: '12px', lineHeight: '1.3' }}>
        {box.fieldName}: {box.fieldValue}
        {box.confidence && box.confidence !== 'high' && (
          <>
            <br />
            Confidence: {box.confidence}
          </>
        )}
      </span>
    );
  };

  let zIndex: number;
  if (box.isParentBox) {
    zIndex = 1000;
  } else if (isHovered || isSelected) {
    zIndex = 2000;
  } else {
    zIndex = 1500;
  }

  const boxShadow = isHovered || isSelected ? '0 2px 8px rgba(0, 0, 0, 0.2)' : 'none';
  const transform = isHovered || isSelected ? 'scale(1.02)' : 'scale(1)';

  let opacity: number;
  if (box.isParentBox) {
    opacity = 0;
  } else if (isHovered || isSelected) {
    opacity = 1;
  } else {
    opacity = 0.9;
  }

  const boxElement = (
    <Box
      borderRadius="$1"
      style={{
        position: 'absolute',
        cursor: box.isParentBox || isParseBox ? 'default' : 'pointer',
        left: box.coords.left,
        top: box.coords.top,
        width: box.coords.width,
        height: box.coords.height,
        zIndex,
        transition: box.isParentBox ? 'none' : 'all 0.2s ease-in-out',
        background: getBackgroundColor(),
        border: '2px solid',
        borderColor: getBorderColor(),
        boxShadow,
        transform,
        opacity,
        pointerEvents: box.isParentBox ? 'none' : 'auto',
      }}
      onMouseEnter={() => !box.isParentBox && setIsHovered(true)}
      onMouseLeave={() => !box.isParentBox && setIsHovered(false)}
      onClick={handleClick}
    />
  );

  if (box.isParentBox) return boxElement;

  return (
    <Tooltip text={getTooltipText()} placement="top" maxWidth={300}>
      {boxElement}
    </Tooltip>
  );
};

export const AnnotationOverlay: FC<AnnotationOverlayProps> = ({
  pageNumber,
  pageWidth,
  pageHeight,
  scale,
  parseData,
  extractedData,
  showingParseBoxes,
  selectedFieldId,
  onFieldSelect,
}) => {
  const [boundingBoxes, setBoundingBoxes] = useState<BoundingBox[]>([]);

  const handleBoxClick = useCallback(
    (fieldId: string) => {
      if (!onFieldSelect) return;
      const newSelectedId = selectedFieldId === fieldId ? null : fieldId;
      onFieldSelect(newSelectedId);
    },
    [selectedFieldId, onFieldSelect],
  );

  useEffect(() => {
    let boxes: BoundingBox[] = [];

    // Generate boxes based on what data is available
    if (showingParseBoxes && parseData) {
      boxes = parseDataToBoundingBoxes(parseData, pageNumber, pageWidth, pageHeight, scale);
    } else if (extractedData) {
      boxes = extractDataToBoundingBoxes(extractedData, pageNumber, pageWidth, pageHeight, scale);
    }

    // Post-process: deduplicate and mark parent boxes
    boxes = deduplicateBoundingBoxes(boxes);
    boxes = markParentBoxes(boxes);

    setBoundingBoxes(boxes);
  }, [pageNumber, pageWidth, pageHeight, scale, parseData, extractedData, showingParseBoxes]);

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
        {boundingBoxes.map((box) => (
          <Box key={`citation-overlay-${box.fieldId}`} style={{ pointerEvents: 'auto' }}>
            <BoundingBoxComponent
              box={box}
              isParseBox={showingParseBoxes}
              selectedFieldId={selectedFieldId}
              onBoxClick={handleBoxClick}
            />
          </Box>
        ))}
      </Box>
    </Box>
  );
};
