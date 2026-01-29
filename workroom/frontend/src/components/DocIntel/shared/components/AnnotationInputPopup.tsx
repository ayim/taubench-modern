import { Box, Button, Input, Typography } from '@sema4ai/components';
import { FC, useState, useEffect, useRef } from 'react';
import { Annotation } from '../hooks/usePdfAnnotations';

interface AnnotationInputPopupProps {
  annotation: Partial<Annotation>;
  onSave: (fieldName: string, fieldValue: string) => void;
  onCancel: () => void;
  position: { x: number; y: number };
}

export const AnnotationInputPopup: FC<AnnotationInputPopupProps> = ({ annotation, onSave, onCancel, position }) => {
  const [fieldName, setFieldName] = useState<string>('');
  const [description, setDescription] = useState<string>('');
  const inputRef = useRef<HTMLInputElement>(null);
  const popupRef = useRef<HTMLDivElement>(null);

  // Initialize with truncated version of selected text
  useEffect(() => {
    if (annotation.selectedText && annotation.selectedText.trim()) {
      // Truncate to first 5 words or 50 characters, whichever is shorter
      const text = annotation.selectedText.trim();
      const words = text.split(/\s+/).slice(0, 5).join(' ');
      const truncated = words.length > 50 ? words.substring(0, 50) : words;
      setFieldName(truncated);
    }
  }, [annotation.selectedText]);

  // Focus the input when popup appears
  useEffect(() => {
    // Focus the input after a short delay to ensure it's rendered
    setTimeout(() => inputRef.current?.focus(), 100);
  }, []);

  // Handle clicks outside the popup to close it
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (popupRef.current && !popupRef.current.contains(event.target as Node)) {
        onCancel();
      }
    };

    // Add event listener after a short delay to avoid closing immediately
    const timer = setTimeout(() => {
      document.addEventListener('mousedown', handleClickOutside, true); // Use capture phase
    }, 200);

    return () => {
      clearTimeout(timer);
      document.removeEventListener('mousedown', handleClickOutside, true);
    };
  }, [onCancel]);

  const handleSave = () => {
    const trimmedFieldName = fieldName.trim();
    const trimmedDescription = description.trim();

    if (trimmedFieldName && trimmedDescription) {
      // Pass description first, then field name (to match the handler signature)
      onSave(trimmedDescription, trimmedFieldName);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && fieldName.trim() && description.trim()) {
      handleSave();
    } else if (e.key === 'Escape') {
      onCancel();
    }
  };

  // Calculate position to keep popup near selection
  // Position prop contains viewport coordinates (x, y) where the popup should appear
  const popupWidth = 500;
  const popupHeight = 140; // Taller to fit two input fields
  const viewportPadding = 20;

  // Center horizontally below the selection
  let left = position.x - popupWidth / 2;
  let top = position.y;

  // Adjust horizontal position to stay on screen
  if (left < viewportPadding) {
    left = viewportPadding;
  } else if (left + popupWidth > window.innerWidth - viewportPadding) {
    left = window.innerWidth - popupWidth - viewportPadding;
  }

  // Adjust vertical position
  if (top + popupHeight > window.innerHeight - viewportPadding) {
    // Not enough space below - position above selection instead
    top = position.y - popupHeight - 20;

    // Ensure we don't go off top
    if (top < viewportPadding) {
      top = viewportPadding;
    }
  }

  return (
    <div
      ref={popupRef}
      style={{
        position: 'fixed',
        left: `${left}px`,
        top: `${top}px`,
        zIndex: 9999,
        width: '500px',
        borderRadius: '8px',
        padding: '12px',
        transform: 'none',
        transformOrigin: 'top left',
        backgroundColor: 'white',
        boxShadow: 'rgba(0, 0, 0, 0.28) 0px 4px 12px',
      }}
    >
      <Box
        display="flex"
        flexDirection="column"
        gap="$8"
        style={{
          position: 'relative',
          width: '100%',
        }}
      >
        {/* Field Name Input */}
        <Box style={{ flex: 1, width: '100%' }}>
          <Typography fontSize="$12" color="content.subtle" style={{ marginBottom: '4px' }}>
            Field Name (will be sanitized)
          </Typography>
          <Input
            ref={inputRef}
            aria-label="Field name"
            placeholder="e.g., company_name, serial_number..."
            value={fieldName}
            onChange={(e) => setFieldName(e.target.value)}
            onKeyDown={handleKeyPress}
            style={{
              width: '100%',
            }}
          />
        </Box>

        {/* Description Input */}
        <Box style={{ flex: 1, width: '100%' }}>
          <Typography fontSize="$12" color="content.subtle" style={{ marginBottom: '4px' }}>
            Description (instructions for AI)
          </Typography>
          <Input
            aria-label="Field description"
            placeholder="e.g., Company name at top of header..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            onKeyDown={handleKeyPress}
            style={{
              width: '100%',
            }}
          />
        </Box>

        {/* Add Field Button */}
        <Box style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '4px' }}>
          <Button
            variant="primary"
            onClick={handleSave}
            disabled={!fieldName.trim() || !description.trim()}
            size="small"
            round
          >
            Add Field
          </Button>
        </Box>
      </Box>
    </div>
  );
};
