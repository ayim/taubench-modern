import { Box, Button, Menu } from '@sema4ai/components';
import { IconDotsHorizontalCircle } from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';
import { useCallback, useEffect, useRef, useState } from 'react';
import type { View } from 'vega';
import embed, { VisualizationSpec } from 'vega-embed';

import { useToggle } from '../../../../../hooks';
import { SEMA4AI_VEGA_LITE_THEME, SEMA4AI_VEGA_THEME, processChartSpecOverrides } from './components/theming';
import LoadingBox from './components/Loading';
import { Code } from '../../../../../common/code';

const VEGA_BASE_URL = 'https://vega.github.io/schema/vega';
const VEGA_LITE_BASE_URL = 'https://vega.github.io/schema/vega-lite';

export const isVegaChartBlock = (lang?: string, text?: string, raw?: string) => {
  // Case 1: There's a lang set on the code block and it's either vega or vega-lite
  if (lang === 'vega' || lang === 'vega-lite') {
    return true;
  }

  // Case 2: The raw text starts and ends with ``` and so the code block is complete
  const isCompleteCodeBlock = raw?.startsWith('```') && raw?.endsWith('```');
  if (isCompleteCodeBlock) {
    // In such a case, we need the JSON within to parse and that parsed JSON
    // needs to pass a strict schema check
    try {
      const parsedSpec = JSON.parse(text ?? '');
      const vegaSchemaRegex = new RegExp(`^${VEGA_BASE_URL}/v[2-5](\\.[0-9]+)?(\\.[0-9]+)?\\.json$`);
      const vegaLiteSchemaRegex = new RegExp(`^${VEGA_LITE_BASE_URL}/v[2-5](\\.[0-9]+)?(\\.[0-9]+)?\\.json$`);

      // Passed stricter schema check?
      return vegaSchemaRegex.test(parsedSpec.$schema) || vegaLiteSchemaRegex.test(parsedSpec.$schema);
    } catch {
      // If we are a complete code block, but failing to parse, then
      // we will _not_ be rendering this as a chart
      return false;
    }
  }

  // Case 3: Streaming case
  // We'll need to try and ascertain whether we are being streamed a chart...
  // we can only do this via heuristics; let's check:
  // (a): Does the text contain an appropriate $schema property
  // (b): Does the text seem to be JSON (should start with { modulo whitespace)
  const hasSchema = Boolean(text?.includes('$schema": "https://vega.github.io/schema/vega'));
  const startsLikeJson = Boolean(text?.trimStart().startsWith('{'));
  return hasSchema && startsLikeJson;
};

const Container = styled(Box)<{ $menuOpen: boolean }>`
  position: relative;
  width: 100%;

  &:before {
    content: '';
    position: absolute;
    top: 0;
    left: -40px;
    width: 40px;
    height: 100%;
  }

  > button {
    display: ${({ $menuOpen }) => ($menuOpen ? 'block' : 'none')};
  }

  &:hover {
    > button {
      display: block;
    }
  }

  ${({ theme }) => theme.screen.m} {
    &:before {
      display: none;
    }

    canvas {
      width: 100% !important;
      height: auto !important;
    }
  }
`;

const ChartTriggerMenu = styled(Button)`
  position: absolute;
  top: 0;
  left: -${({ theme }) => theme.space.$40};
`;

interface ChartProps {
  spec: string;
}

export const Chart = ({ spec }: ChartProps) => {
  const [isChartReady, setIsChartReady] = useState(false);
  const { val: showSource, toggle: toggleShowSource } = useToggle(false);
  const chartRef = useRef<HTMLDivElement>(null);
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef<View | null>(null);
  const charContextMenuBtnRef = useRef<HTMLButtonElement>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  const handleExport = useCallback(async (format: 'svg' | 'png') => {
    if (!viewRef.current) return;

    try {
      const link = document.createElement('a');
      link.download = `chart.${format}`;

      const view = viewRef.current;
      const currentBackground = view.background();

      await new Promise<void>((resolve) => {
        requestAnimationFrame(async () => {
          view.background('white');
          link.href = await view.toImageURL(format);
          resolve();
        });
      });

      requestAnimationFrame(() => {
        view.background(currentBackground);
        view.run();
      });

      link.click();
    } catch {
      // Fall through to loading state
    }
  }, []);

  const handlePNGExport = useCallback(() => {
    handleExport('png');
  }, [handleExport]);

  const handleSVGExport = useCallback(() => {
    handleExport('svg');
  }, [handleExport]);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    if (showSource) {
      chartContainerRef.current.innerHTML = '';
      return;
    }

    try {
      const contentAsJson = JSON.parse(spec);
      const hasSchema = Boolean(contentAsJson.$schema);

      if (hasSchema) {
        const processedSpec = processChartSpecOverrides(contentAsJson);
        const isVegaLite = processedSpec.$schema?.includes(VEGA_LITE_BASE_URL);
        const theme = isVegaLite ? SEMA4AI_VEGA_LITE_THEME : SEMA4AI_VEGA_THEME;

        const specWithTheme = {
          ...processedSpec,
          config: {
            ...theme,
            ...(processedSpec.config || {}),
          },
        } as VisualizationSpec;

        embed(chartContainerRef.current, specWithTheme, {
          renderer: 'canvas',
          actions: false,
        }).then((result) => {
          viewRef.current = result.view;
          setIsChartReady(true);
        });
      }
    } catch {
      // Fall through to loading state
    }
  }, [spec, showSource]);

  try {
    const contentAsJson = JSON.parse(spec);
    const hasSchema = Boolean(contentAsJson.$schema);

    if (hasSchema) {
      return (
        <Container $menuOpen={menuOpen} ref={chartRef}>
          {showSource && <Code maxRows={16} value={JSON.stringify(contentAsJson, null, 2)} lang="json" />}

          <Box data-testid="chart-canvas-container">
            {!isChartReady && (
              <Box>
                <LoadingBox />
              </Box>
            )}
            <Box ref={chartContainerRef} />
          </Box>

          <Menu
            trigger={
              <ChartTriggerMenu
                ref={charContextMenuBtnRef}
                aria-label="chart-context-menu"
                variant="ghost-subtle"
                icon={IconDotsHorizontalCircle}
                iconSize={32}
                round
              />
            }
            visible={menuOpen}
            setVisible={setMenuOpen}
          >
            <Menu.Item onClick={handleSVGExport}>Save as SVG</Menu.Item>
            <Menu.Item onClick={handlePNGExport}>Save as PNG</Menu.Item>
            <Menu.Item onClick={toggleShowSource}>{showSource ? 'Show Chart' : 'Show Source'}</Menu.Item>
          </Menu>
        </Container>
      );
    }
  } catch {
    // Fall through to loading state
  }

  return <LoadingBox />;
};
