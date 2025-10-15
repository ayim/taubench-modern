import { Box, Button, Typography, Popover, PopoverTriggerProps, Input } from '@sema4ai/components';
import { IconClose } from '@sema4ai/icons';
import { FC, useState, useEffect, useCallback, useRef } from 'react';

const PLACEHOLDER_MESSAGE = `Add notes for special handling of this field here.

You can also annotate in the document viewer to specify your instruction.`;

interface SpecialHandlingMenuProps {
  fieldId: string;
  fieldName: string;
  currentInstructions?: string;
  onSave: (fieldId: string, instructions: string) => void;
  onCancel: () => void;
  trigger: React.ReactNode;
  label?: string; // Add optional label prop
}

export const SpecialHandlingMenu: FC<SpecialHandlingMenuProps> = ({
  fieldId,
  fieldName,
  currentInstructions = '',
  onSave,
  onCancel,
  trigger,
  label = 'Field', // Default to 'Field' for backward compatibility
}) => {
  const [instructions, setInstructions] = useState<string>(currentInstructions);
  const closePopoverTrigger = useRef<(() => void) | null>(null);

  const poptrigger = useCallback(
    ({ toggle, referenceProps, referenceRef, closePopover }: PopoverTriggerProps) => {
      closePopoverTrigger.current = closePopover;
      return (
        <Box ref={referenceRef} {...referenceProps} onClick={toggle}>
          {trigger}
        </Box>
      );
    },
    [trigger],
  );

  const handleCancel = useCallback(() => {
    closePopoverTrigger.current?.();
    setTimeout(() => onCancel(), 100);
  }, [onCancel]);

  const handleSave = useCallback(() => {
    onSave(fieldId, instructions.trim());
    closePopoverTrigger.current?.();
  }, [fieldId, instructions, onSave]);

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setInstructions(e.target.value);
  }, []);

  // Update instructions when currentInstructions prop changes
  useEffect(() => {
    if (currentInstructions) {
      setInstructions(currentInstructions);
    }
  }, [currentInstructions]);

  return (
    <Popover trigger={poptrigger} minWidth={450} placement="bottom-start">
      <Box className="hover:!bg-transparent !cursor-default !p-0" onClick={(e) => e.stopPropagation()}>
        <Box padding="$16" minWidth="400px" maxWidth="500px" onClick={(e) => e.stopPropagation()}>
          {/* Header */}
          <Box display="flex" alignItems="center" justifyContent="space-between" marginBottom="$16">
            <Typography id="special-handling-instructions" fontSize="$18" fontWeight="bold" color="content.primary">
              Special Handling Instructions
            </Typography>
            <Button size="small" variant="ghost" onClick={handleCancel} className="text-gray-400 hover:text-gray-600">
              <IconClose />
            </Button>
          </Box>

          {/* Field Name Display */}
          <Box marginBottom="$16">
            <Typography fontSize="$14" fontWeight="medium" marginBottom="$4">
              {label}: {fieldName}
            </Typography>
          </Box>

          {/* Instructions Input using Menu.Input */}
          <Box marginBottom="$20">
            <Input
              aria-labelledby="special-handling-instructions"
              rows={8}
              placeholder={PLACEHOLDER_MESSAGE}
              value={instructions}
              onChange={handleChange}
            />
          </Box>

          {/* Action Buttons */}
          <Box display="flex" gap="$12" justifyContent="flex-end">
            <Button round variant="outline" onClick={handleCancel}>
              Cancel
            </Button>
            <Button round variant="primary" onClick={handleSave} disabled={!instructions.trim()}>
              Save
            </Button>
          </Box>
        </Box>
      </Box>
    </Popover>
  );
};
