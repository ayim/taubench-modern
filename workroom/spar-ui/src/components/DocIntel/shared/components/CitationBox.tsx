import { Box, Tooltip } from '@sema4ai/components';
import { FC, useState } from 'react';

export interface CitationBoxProps {
  coords: { left: number; top: number; width: number; height: number };
  fieldName: string;
  fieldValue: string;
  fieldId: string;
  selectedFieldId?: string | null;
  onBoxClick?: (fieldId: string) => void;
  onHoverChange?: (fieldId: string | null) => void;
  isMatched?: boolean;
  isParentBox?: boolean;
  isParseBox?: boolean;
  type?: string;
  confidence?: string;
}

export const CitationBox: FC<CitationBoxProps> = ({
  coords,
  fieldName,
  fieldValue,
  fieldId,
  selectedFieldId,
  onBoxClick,
  onHoverChange,
  isMatched = false,
  isParentBox = false,
  isParseBox = false,
  type,
  confidence,
}) => {
  const [isHovered, setIsHovered] = useState(false);
  const isSelected = fieldId === selectedFieldId;

  const handleBoxClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isParentBox || isParseBox) return;
    if (onBoxClick && fieldId) {
      onBoxClick(fieldId);
    }
  };

  const handleMouseEnter = () => {
    if (isParentBox) return;
    setIsHovered(true);
    if (onHoverChange) {
      onHoverChange(fieldId);
    }
  };

  const handleMouseLeave = () => {
    if (isParentBox) return;
    setIsHovered(false);
    if (onHoverChange) {
      onHoverChange(null);
    }
  };

  const getTooltipText = () => {
    if (isParseBox && type) {
      return (
        <span style={{ fontSize: '12px', lineHeight: '1.3' }}>
          Type: {type}
          {confidence && confidence !== 'high' && (
            <>
              <br />
              Confidence: {confidence}
            </>
          )}
        </span>
      );
    }

    const cleanFieldName = fieldName.replace(/\[\d+\]/g, '');
    return (
      <span style={{ fontSize: '12px', lineHeight: '1.3' }}>
        {cleanFieldName}: {fieldValue}
        {confidence && confidence !== 'high' && (
          <>
            <br />
            Confidence: {confidence}
          </>
        )}
      </span>
    );
  };

  const getBorderColor = () => {
    if (isParentBox) return 'transparent';

    if (isParseBox) {
      switch (type?.toLowerCase()) {
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

    return 'rgb(22, 140, 43)'; // Green for extract citations
  };

  const getBackgroundColor = () => {
    if (isParentBox) return 'transparent';

    if (isHovered || isSelected) return 'transparent';

    if (isParseBox) {
      switch (type?.toLowerCase()) {
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

    if (isMatched) return 'rgb(39 214 60 / 20%)';
    return 'rgb(39 214 60 / 20%)';
  };

  // Extract nested ternary expressions to variables
  let zIndex: number;
  if (isParentBox) {
    zIndex = 1000;
  } else if (isHovered || isSelected) {
    zIndex = 2000;
  } else {
    zIndex = 1500;
  }

  let boxShadow: string;
  if (isParentBox) {
    boxShadow = 'none';
  } else if (isHovered || isSelected) {
    boxShadow = '0 2px 8px rgba(0, 0, 0, 0.2)';
  } else {
    boxShadow = 'none';
  }

  let transform: string;
  if (isParentBox) {
    transform = 'none';
  } else if (isHovered || isSelected) {
    transform = 'scale(1.02)';
  } else {
    transform = 'scale(1)';
  }

  let opacity: number;
  if (isParentBox) {
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
        cursor: isParentBox ? 'default' : 'pointer',
        left: coords.left,
        top: coords.top,
        width: coords.width,
        height: coords.height,
        zIndex,
        transition: isParentBox ? 'none' : 'all 0.2s ease-in-out',
        background: getBackgroundColor(),
        border: '2px solid',
        borderColor: getBorderColor(),
        boxShadow,
        transform,
        opacity,
        pointerEvents: isParentBox ? 'none' : 'auto',
      }}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onClick={handleBoxClick}
    />
  );

  if (isParentBox) {
    return boxElement;
  }

  return (
    <Tooltip text={getTooltipText()} placement="top" maxWidth={300}>
      {boxElement}
    </Tooltip>
  );
};
