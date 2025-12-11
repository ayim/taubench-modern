import { FC } from 'react';
import { Box, Typography } from '@sema4ai/components';
import { Chart } from '../interactionComponents/chart';
import { Spinner } from '../renderer/InlineWidgets';
import { Thinking } from '../renderer/Thinking';

type Props = {
  spec?: string;
  status: string;
  description?: string;
  error?: string | null;
  thinking?: string;
};

export const ChartInlineMount: FC<Props> = ({ spec, status, description, error, thinking }) => {
  const lowerStatus = (status || '').toLowerCase();

  // If done, render the actual chart
  if (lowerStatus === 'done' && spec) {
    return <Chart spec={spec} />;
  }

  // Visual cues
  const isError = !!error;
  const isLoading = !isError;

  return (
    <Box
      display="flex"
      flexDirection="column"
      borderRadius="$16"
      borderColor="border.subtle"
      overflow="hidden" // Ensures the internal backgrounds don't bleed out
      style={{
        // A cleaner, glass-like background
        background: 'rgba(255, 255, 255, 0.6)',
        backdropFilter: 'blur(10px)',
        boxShadow: '0 4px 20px rgba(0,0,0,0.04)',
        transition: 'all 0.2s ease',
      }}
    >
      {/* 1. Header: The Description (Prominent) */}
      <Box padding="$4" paddingBottom="$2">
        <Typography variant="body-medium" color="content.subtle" style={{ display: 'block', marginBottom: 4 }}>
          {description || 'Generating visualization...'}
        </Typography>
      </Box>

      {/* 2. Body: The Visual Placeholder (Prevents layout shift) */}
      <Box
        display="flex"
        alignItems="center"
        justifyContent="center"
        gap="$3"
        height="200px" // Mimics the height of a typical chart to prevent jumpiness
        margin="$4"
        marginTop="0"
        borderRadius="$16"
        backgroundColor="background.subtle"
        style={{
          border: '1px dashed rgba(0,0,0,0.1)', // Subtle dashed border implies "placeholder"
        }}
      >
        {isError ? (
          <Typography variant="body-medium">{error || 'Error generating chart'}</Typography>
        ) : (
          <>
            <Spinner />
            <Typography paddingLeft="$4" variant="body-medium" color="content.subtle">
              Generating chart...
            </Typography>
          </>
        )}
      </Box>

      {/* 3. Footer: The "Thinking" Stream (Visible but subtle) */}
      {thinking && isLoading && (
        <Box
          padding="$4"
          paddingLeft="$8"
          backgroundColor="background.subtle"
          borderColor="border.subtle"
          display="flex"
          alignItems="flex-start" // Align top in case text wraps
          gap="$2"
        >
          <Box flex={1}>
            <Thinking complete={false} platform="openai">
              {thinking}
            </Thinking>
          </Box>
        </Box>
      )}
    </Box>
  );
};
