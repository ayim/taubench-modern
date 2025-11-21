import { FC, useState } from 'react';
import { Box, Typography, Input } from '@sema4ai/components';

/**
 * ExtractionPromptEditor - Edit extraction prompt
 * Phase 1: Power user configuration approach
 */

export interface AdditionalExtractionInfo {
  label: string;
  context: string;
}

interface ExtractionPromptEditorProps {
  initialPrompt?: string;
  additionalInfo?: AdditionalExtractionInfo[];
  onChange?: (prompt: string, additionalInfo: AdditionalExtractionInfo[]) => void;
  disabled?: boolean;
}

export const ExtractionPromptEditor: FC<ExtractionPromptEditorProps> = ({
  initialPrompt = '',
  additionalInfo = [],
  onChange,
  disabled = false,
}) => {
  const [prompt, setPrompt] = useState(initialPrompt);

  const handlePromptChange = (value: string) => {
    setPrompt(value);
    onChange?.(value, additionalInfo);
  };

  return (
    <Box display="flex" flexDirection="column" gap="$16" padding="$16">
      {/* Main Extraction Prompt */}
      <Box display="flex" flexDirection="column" gap="$8">
        <Typography fontSize="$14" fontWeight="bold">
          Business Instructions
        </Typography>
        <Input
          label=""
          value={prompt}
          onChange={(e) => handlePromptChange(e.target.value)}
          placeholder="Enter business instructions..."
          disabled={disabled}
          rows={6}
          autoGrow
          style={{ fontSize: '13px' }}
        />
      </Box>
    </Box>
  );
};
