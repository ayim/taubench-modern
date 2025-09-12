import { FC, useCallback, useMemo, useRef } from 'react';
import type { View } from 'vega';
import { VisualizationSpec } from 'vega-embed';

import { useParams, useToggle } from '../../../../../hooks';
import { SEMA4AI_VEGA_LITE_THEME, SEMA4AI_VEGA_THEME, processChartSpecOverrides } from './components/theming';
import LoadingBox from './components/Loading';
import { ChartContainer } from './components/Container';
import { ChartEmbed } from './components/Embed';
import { useDataFrameQuery } from '../../../../../queries/dataFrames';
import { specHasDataFrameUrl } from './components/utils';

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

const ChartContent: FC<{ rawSpec: VisualizationSpec | null; themedSpec: VisualizationSpec | null }> = ({
  rawSpec,
  themedSpec,
}) => {
  const { val: showSource, toggle: toggleShowSource } = useToggle(false);
  const viewRef = useRef<View | null>(null);

  const hasSchema = themedSpec !== null && rawSpec !== null;
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

  const onEmbed = useCallback((view: View) => {
    viewRef.current = view;
  }, []);

  if (hasSchema) {
    return (
      <ChartContainer
        handleExport={handleExport}
        spec={rawSpec}
        showSource={showSource}
        onToggleShowSource={toggleShowSource}
      >
        <ChartEmbed showSource={showSource} themedSpec={themedSpec} onEmbed={onEmbed} />
      </ChartContainer>
    );
  }

  return <LoadingBox />;
};

const DataFrameChart: FC<{ themedSpec: VisualizationSpec; rawSpec: VisualizationSpec; dataFrameName: string }> = ({
  themedSpec,
  rawSpec,
  dataFrameName,
}) => {
  const { threadId } = useParams('/thread/$agentId/$threadId');
  const { data, isLoading } = useDataFrameQuery({ threadId, dataFrameName });

  const patchedSpecs = useMemo(() => {
    const patchedData = { values: data };
    return {
      patchedThemedSpec: {
        ...themedSpec,
        data: patchedData,
      } as VisualizationSpec,
      patchedRawSpec: {
        ...rawSpec,
        data: patchedData,
      } as VisualizationSpec,
    };
  }, [data]);

  if (isLoading) {
    return <LoadingBox />;
  }

  return <ChartContent rawSpec={patchedSpecs.patchedRawSpec} themedSpec={patchedSpecs.patchedThemedSpec} />;
};

interface ChartProps {
  spec: string;
}

export const Chart = ({ spec }: ChartProps) => {
  const specData = useMemo<
    | { contentAsJson: VisualizationSpec; themedSpec: VisualizationSpec; hasSchema: true; dataFrameName?: string }
    | { contentAsJson: null; themedSpec: null; hasSchema: false; dataFrameName: null }
  >(() => {
    const failureResult = { contentAsJson: null, themedSpec: null, hasSchema: false as const, dataFrameName: null };
    try {
      const parsedSpec = JSON.parse(spec);
      const hasSchema = Boolean(parsedSpec.$schema);

      if (!hasSchema) return failureResult;

      const processedSpec = processChartSpecOverrides(parsedSpec);
      const isVegaLite = processedSpec.$schema?.includes(VEGA_LITE_BASE_URL);
      const theme = isVegaLite ? SEMA4AI_VEGA_LITE_THEME : SEMA4AI_VEGA_THEME;

      const specWithTheme = {
        ...processedSpec,
        config: {
          ...theme,
          ...(processedSpec.config || {}),
        },
      } as VisualizationSpec;

      const dataFrameNameUrlMatch = specHasDataFrameUrl(specWithTheme);
      return {
        contentAsJson: parsedSpec,
        themedSpec: specWithTheme,
        hasSchema,
        dataFrameName: dataFrameNameUrlMatch?.dataFrameName,
      };
    } catch {
      return failureResult;
    }
  }, [spec]);

  if (specData.dataFrameName) {
    return (
      <DataFrameChart
        themedSpec={specData.themedSpec}
        rawSpec={specData.contentAsJson}
        dataFrameName={specData.dataFrameName}
      />
    );
  }

  return <ChartContent rawSpec={specData.contentAsJson} themedSpec={specData.themedSpec} />;
};
