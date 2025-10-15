import { Box, Button, Input, Typography } from '@sema4ai/components';
import { IconCheckCircle, IconPencil } from '@sema4ai/icons';
import { FC, useCallback, useEffect, useState } from 'react';
import Collapsible from './Collapsible';

interface SpecialHandlingInstructionsProps {
  step: 'document_layout' | 'data_model' | 'data_quality';
  objectPrompt?: string | null;
  disabled?: boolean;
  onUpdate?: (prompt: string) => void;
}

export const SpecialHandlingInstructions: FC<SpecialHandlingInstructionsProps> = ({
  step,
  objectPrompt,
  disabled = false,
  onUpdate,
}) => {
  const [prompt, setPrompt] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  // Handle Update
  const handleUpdate = useCallback(
    async (newPrompt: string) => {
      setPrompt(newPrompt);
      setIsProcessing(true);

      // Use setTimeout to simulate debounced behavior
      setTimeout(() => {
        if (onUpdate) {
          onUpdate(newPrompt);
        }
        setIsProcessing(false);
      }, 300);
    },
    [onUpdate],
  );

  useEffect(() => {
    if (objectPrompt) {
      setPrompt(objectPrompt);
    }
  }, [objectPrompt]);

  const getPlaceholderText = () => {
    switch (step) {
      case 'data_model':
        return 'Enter instructions to help process and generate the data model.';
      case 'document_layout':
        return 'Enter instructions to help process and generate the document layout.';
      case 'data_quality':
        return 'Enter instructions to help process and generate the data quality checks.';
      default:
        return '';
    }
  };

  return (
    <Box marginTop="$16" marginBottom="$16">
      <Collapsible
        header={
          <Box display="flex" alignItems="center" gap="$8">
            <IconPencil color="content.subtle" size={20} />
            <Typography fontSize="$16" fontWeight="medium">
              Special Handling Instructions
            </Typography>
          </Box>
        }
      >
        <Box display="flex" flexDirection="column" gap="$12">
          <Box className="w-full" style={{ position: 'relative' }}>
            <Input
              label=""
              placeholder={getPlaceholderText()}
              value={prompt}
              onChange={(e) => {
                handleUpdate(e.target.value);
              }}
              rows={6}
              autoGrow
              className="w-full"
              style={{ paddingRight: '80px', paddingBottom: '50px' }}
              disabled={disabled}
            />
            <Box
              style={{
                position: 'absolute',
                bottom: '8px',
                right: '8px',
                zIndex: '10',
              }}
            >
              <Button
                aria-label="Update"
                onClick={() => handleUpdate(prompt)}
                disabled={!prompt.trim() || isProcessing || disabled}
                variant="outline"
                size="small"
                icon={IconCheckCircle}
                loading={isProcessing}
                round
              />
            </Box>
          </Box>
        </Box>
      </Collapsible>
    </Box>
  );
};
