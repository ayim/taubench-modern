import { FC, useEffect, useRef, useState } from 'react';
import type { View } from 'vega';
import embed, { VisualizationSpec } from 'vega-embed';
import { Box } from '@sema4ai/components';

import LoadingBox from './Loading';

interface ChartEmbedProps {
  showSource: boolean;
  themedSpec: VisualizationSpec | null;
  onEmbed: (view: View) => void;
}

export const ChartEmbed: FC<ChartEmbedProps> = ({ showSource, themedSpec, onEmbed }) => {
  const [isChartReady, setIsChartReady] = useState(false);

  const chartContainerRef = useRef<HTMLDivElement>(null);

  const hasSchema = themedSpec !== null;

  useEffect(() => {
    if (!chartContainerRef.current) return;

    if (showSource) {
      chartContainerRef.current.innerHTML = '';
      return;
    }

    try {
      if (hasSchema) {
        embed(chartContainerRef.current, themedSpec, {
          renderer: 'canvas',
          actions: false,
        }).then((result) => {
          onEmbed(result.view);
          setIsChartReady(true);
        });
      }
    } catch {
      // Fall through to loading state
    }
  }, [themedSpec, showSource]);

  if (hasSchema) {
    return (
      <>
        {!isChartReady && (
          <Box>
            <LoadingBox />
          </Box>
        )}
        <Box ref={chartContainerRef} />
      </>
    );
  }

  return <LoadingBox />;
};
